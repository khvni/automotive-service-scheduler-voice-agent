# Calendar Integration Improvement Task

## Background

You are a background coding agent tasked with fixing critical issues in the Google Calendar integration for an automotive voice agent application. The current implementation has several severe problems:

1. **Mock calendar availability checks** - The system doesn't actually check Google Calendar
2. **No calendar event creation** - Appointments are only saved to the database, not Google Calendar
3. **Inconsistent authentication** - Two different auth methods exist (service account vs OAuth2)
4. **Orphaned code** - Unused calendar_tools.py file
5. **Missing tool integration** - Calendar functions not properly exposed to the LLM

## Reference Implementations (Working, Tested, Production-Ready)

These are your sources of truth. Study them carefully:

### 1. duohub-ai/google-calendar-voice-agent (PRIMARY REFERENCE)

**calendar_service.py** - The gold standard implementation:

```python
import os
import asyncio
from loguru import logger
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class CalendarService:
    def __init__(self):
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.aedt = ZoneInfo("Australia/Sydney")  # Use appropriate timezone

    # Start callbacks for immediate user feedback
    async def start_get_free_availability(self, function_name, llm, context):
        """Push a frame to the LLM; this is handy when the LLM response might take a while."""
        await llm.push_frame(TTSSpeakFrame("Sure. Just a moment."))
        logger.debug(f"Starting get_free_availability with function_name: {function_name}")

    async def start_create_calendar_event(self, function_name, llm, context):
        """Push a frame to the LLM while creating calendar event"""
        await llm.push_frame(TTSSpeakFrame("Scheduling your event now."))
        logger.debug(f"Starting create_calendar_event with function_name: {function_name}")

    # Handler functions
    async def handle_get_free_availability(self, function_name, tool_call_id, args, llm, context, result_callback):
        logger.info(f"get_free_availability called with args: {args}")
        result = await self.get_free_availability(
            start_time_str=args['start_time'],
            end_time_str=args['end_time']
        )
        await result_callback(result)

    async def handle_create_calendar_event(self, function_name, tool_call_id, args, llm, context, result_callback):
        logger.info(f"create_calendar_event called with args: {args}")
        result = await self.create_calendar_event(
            title=args['title'],
            start_time_str=args['start_time'],
            description=args.get('description', ''),
            attendees=args.get('attendees')
        )
        await result_callback(result)

    def get_calendar_service(self):
        logger.debug(f"Starting get_calendar_service with token: {self.refresh_token[:10]}...")
        try:
            creds = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=['https://www.googleapis.com/auth/calendar']
            )
            logger.debug("Created credentials object")

            service = build('calendar', 'v3', credentials=creds)
            logger.debug("Built calendar service successfully")
            return service
        except Exception as e:
            logger.error(f"Error in get_calendar_service: {str(e)}", exc_info=True)
            raise

    async def get_free_availability(self, start_time_str, end_time_str):
        try:
            service = self.get_calendar_service()

            start_time = datetime.fromisoformat(start_time_str).replace(tzinfo=self.aedt)
            end_time = datetime.fromisoformat(end_time_str).replace(tzinfo=self.aedt)

            start_time_utc = start_time.astimezone(timezone.utc)
            end_time_utc = end_time.astimezone(timezone.utc)

            body = {
                'timeMin': start_time_utc.isoformat(),
                'timeMax': end_time_utc.isoformat(),
                'items': [{'id': 'primary'}]
            }

            freebusy_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: service.freebusy().query(body=body).execute()
            )

            free_slots = self._process_freebusy_response(freebusy_response, start_time, end_time)

            if free_slots:
                free_slots_text = "\n".join([
                    f"- Available from {slot['start'].strftime('%I:%M %p')} to {slot['end'].strftime('%I:%M %p')}"
                    for slot in free_slots
                ])
                return {
                    "available_slots": free_slots_text,
                    "count": len(free_slots)
                }
            else:
                return {
                    "available_slots": "No free time slots found in the specified range",
                    "count": 0
                }
        except Exception as e:
            logger.error(f"Error getting free availability: {str(e)}")
            return {
                "available_slots": f"Sorry, I encountered an error: {str(e)}",
                "count": 0
            }

    def _process_freebusy_response(self, freebusy_response, start_time, end_time):
        busy_periods = freebusy_response['calendars']['primary']['busy']
        free_slots = []
        current_time = start_time

        for busy in busy_periods:
            busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00')).astimezone(self.aedt)
            busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00')).astimezone(self.aedt)

            if current_time < busy_start:
                free_slots.append({
                    'start': current_time,
                    'end': busy_start
                })
            current_time = busy_end

        if current_time < end_time:
            free_slots.append({
                'start': current_time,
                'end': end_time
            })

        return free_slots
```

**Key Patterns to Copy:**
1. Use `asyncio.get_event_loop().run_in_executor()` for blocking Google API calls
2. Always handle timezones properly with ZoneInfo
3. OAuth2 refresh token authentication (NOT service account)
4. Handler pattern with result_callback
5. Start callbacks for immediate UX feedback
6. Comprehensive error handling with logging

### 2. Official Google Calendar API Pattern

From alexandrumd/google-calendar-quickstart:

```python
# Proper freebusy query structure
body = {
    "timeMin": timeMin,
    "timeMax": timeMax,
    "timeZone": 'UTC',
    "items": [{"id": calendar_id}]
}

freebusy_result = service.freebusy().query(body=body).execute()
slots = freebusy_result.get('calendars', {}).get(calendar_id, [])
```

## Your Task: Fix the Automotive Voice Calendar Integration

### Files to Modify

1. **DELETE**: `server/app/tools/calendar_tools.py` - This is orphaned code using wrong auth method
2. **MODIFY**: `server/app/tools/crm_tools.py` - Replace mock implementations
3. **MODIFY**: `server/app/services/tool_router.py` - Add calendar tool handlers
4. **MODIFY**: `server/app/services/tool_definitions.py` - Update tool schemas
5. **REVIEW**: `server/app/services/calendar_service.py` - Already exists and is good!
6. **REVIEW**: `server/app/services/calendar_integration.py` - Already exists and is good!

### Step-by-Step Implementation Plan

#### STEP 1: Delete Orphaned Calendar Tools File

```bash
git rm server/app/tools/calendar_tools.py
git add server/app/tools/calendar_tools.py
git commit -m "refactor: remove orphaned calendar_tools.py using wrong auth method"
```

**Reasoning**: This file uses service account auth which conflicts with our OAuth2 approach. It's not used anywhere.

#### STEP 2: Fix get_available_slots in crm_tools.py

**Current code** (server/app/tools/crm_tools.py:245-337):
```python
async def get_available_slots(date: str, duration_minutes: int = 30) -> Dict[str, Any]:
    # ... MOCK IMPLEMENTATION - DOES NOT CHECK GOOGLE CALENDAR ...
    # Line 272 comment: "This is a POC mock implementation. Feature 7 will integrate with Google Calendar"
```

**Replace with**:
```python
async def get_available_slots(date: str, duration_minutes: int = 30) -> Dict[str, Any]:
    """
    Get available appointment slots from Google Calendar for a specific date.

    This function now ACTUALLY checks Google Calendar via CalendarService.
    Business hours:
    - Monday-Friday: 9 AM - 5 PM (excluding 12-1 PM lunch)
    - Saturday: 9 AM - 3 PM (excluding 12-1 PM lunch)
    - Sunday: Closed

    Args:
        date: Date string in YYYY-MM-DD format
        duration_minutes: Minimum slot duration in minutes (default: 30)

    Returns:
        Dict with available slots from actual Google Calendar
    """
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        from app.config import settings
        from app.services.calendar_service import CalendarService

        # Parse and validate date
        slot_date = datetime.fromisoformat(date).date()
        day_of_week = slot_date.strftime("%A")

        # Check if Sunday (closed)
        if slot_date.weekday() == 6:
            return {
                "success": True,
                "date": date,
                "day_of_week": day_of_week,
                "available_slots": [],
                "message": "We are closed on Sundays",
            }

        # Determine business hours
        if slot_date.weekday() < 5:  # Monday-Friday
            start_hour, end_hour = 9, 17  # 9 AM - 5 PM
        else:  # Saturday
            start_hour, end_hour = 9, 15  # 9 AM - 3 PM

        # Initialize calendar service
        calendar = CalendarService(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            timezone_name=settings.TIMEZONE,  # e.g., "America/New_York"
        )

        # Create timezone-aware datetime for the day
        tz = ZoneInfo(settings.TIMEZONE)
        start_time = datetime.combine(slot_date, datetime.min.time()).replace(
            hour=start_hour, minute=0, second=0, microsecond=0, tzinfo=tz
        )
        end_time = datetime.combine(slot_date, datetime.min.time()).replace(
            hour=end_hour, minute=0, second=0, microsecond=0, tzinfo=tz
        )

        # Get free slots from Google Calendar (ACTUAL CALL!)
        result = await calendar.get_free_availability(
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes
        )

        # Format slots for response
        formatted_slots = []
        for slot in result:
            formatted_slots.append({
                "start": slot["start"].isoformat(),
                "end": slot["end"].isoformat(),
                "start_time": slot["start"].strftime("%I:%M %p"),
                "end_time": slot["end"].strftime("%I:%M %p"),
            })

        logger.info(f"Found {len(formatted_slots)} available slots from Google Calendar for {date}")

        return {
            "success": True,
            "date": date,
            "day_of_week": day_of_week,
            "available_slots": formatted_slots,
            "count": len(formatted_slots),
            "message": f"Found {len(formatted_slots)} available time slots",
        }

    except ValueError as e:
        logger.error(f"Invalid date format {date}: {e}")
        return {
            "success": False,
            "error": "Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-15)",
            "message": "Invalid date format",
        }
    except Exception as e:
        logger.error(f"Error getting calendar availability for {date}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "Error checking calendar availability",
        }
```

**Add and commit**:
```bash
git add server/app/tools/crm_tools.py
git commit -m "feat: integrate real Google Calendar availability checks in get_available_slots

- Replace mock implementation with actual CalendarService calls
- Now checks real calendar via freebusy API
- Maintains business hours logic (Mon-Fri 9-5, Sat 9-3, Sun closed)
- Proper timezone handling with ZoneInfo
- Returns formatted slots with human-readable times"
```

#### STEP 3: Fix book_appointment in crm_tools.py

**Current code** (server/app/tools/crm_tools.py:345-onwards) - Only creates DB records

**Replace with** (around line 391, inside the try block after validation):
```python
async def book_appointment(
    db: AsyncSession,
    customer_id: int,
    vehicle_id: int,
    scheduled_at: str,
    service_type: str,
    duration_minutes: int = 60,
    service_description: Optional[str] = None,
    customer_concerns: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Book a service appointment in both database AND Google Calendar.

    This now creates:
    1. Database appointment record
    2. Google Calendar event with customer details

    Args:
        db: Database session
        customer_id: Customer ID
        vehicle_id: Vehicle ID
        scheduled_at: ISO format datetime string (e.g., "2025-01-15T09:00:00")
        service_type: Type of service
        duration_minutes: Appointment duration (default: 60)
        service_description: Optional service description
        customer_concerns: Optional customer concerns
        notes: Optional notes

    Returns:
        Dict with appointment details including calendar event ID
    """
    try:
        from datetime import datetime
        from app.config import settings
        from app.services.calendar_service import CalendarService
        from app.services.calendar_integration import book_appointment_with_calendar

        # Parse scheduled time
        appointment_time = datetime.fromisoformat(scheduled_at)

        # Initialize calendar service
        calendar = CalendarService(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            timezone_name=settings.TIMEZONE,
        )

        # Use the integration layer to book in BOTH DB and Calendar
        result = await book_appointment_with_calendar(
            db=db,
            calendar=calendar,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            service_type=service_type,
            start_time=appointment_time,
            duration_minutes=duration_minutes,
            notes=notes or service_description or customer_concerns,
        )

        if not result["success"]:
            logger.error(f"Failed to book appointment: {result['message']}")
            return result

        logger.info(f"Appointment booked successfully: {result['appointment_id']} with calendar event {result['calendar_event_id']}")

        # Invalidate customer cache since they have a new appointment
        from app.services.redis_client import invalidate_customer_cache
        customer = await db.get(Customer, customer_id)
        if customer:
            await invalidate_customer_cache(customer.phone_number)

        return {
            "success": True,
            "data": {
                "appointment_id": result["appointment_id"],
                "calendar_event_id": result["calendar_event_id"],
                "calendar_link": result["calendar_link"],
                "customer_name": result["customer_name"],
                "vehicle_info": result["vehicle_info"],
                "scheduled_at": result["start_time"],
                "end_time": result["end_time"],
                "service_type": result["service_type"],
                "duration_minutes": duration_minutes,
                "status": "scheduled",
            },
            "message": f"Appointment scheduled successfully. Calendar event created: {result['calendar_link']}",
        }

    except Exception as e:
        logger.error(f"Error booking appointment: {e}", exc_info=True)
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to book appointment",
        }
```

**Add and commit**:
```bash
git add server/app/tools/crm_tools.py
git commit -m "feat: create Google Calendar events when booking appointments

- Use calendar_integration.book_appointment_with_calendar()
- Creates both DB record AND Google Calendar event
- Returns calendar event ID and link
- Invalidates customer cache after booking
- Proper error handling with rollback"
```

#### STEP 4: Fix cancel_appointment in crm_tools.py

**Current implementation** (line 613) - Only updates DB

**Update to**:
```python
async def cancel_appointment(db: AsyncSession, appointment_id: int, reason: str) -> Dict[str, Any]:
    """
    Cancel an appointment in both database AND Google Calendar.

    Args:
        db: Database session
        appointment_id: Appointment ID to cancel
        reason: Cancellation reason

    Returns:
        Dict with cancellation result
    """
    try:
        from app.config import settings
        from app.services.calendar_service import CalendarService
        from app.services.calendar_integration import cancel_appointment_with_calendar

        # Initialize calendar service
        calendar = CalendarService(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            timezone_name=settings.TIMEZONE,
        )

        # Get appointment to find customer for cache invalidation
        appointment = await db.get(Appointment, appointment_id)
        if not appointment:
            return {
                "success": False,
                "error": f"Appointment {appointment_id} not found",
                "message": "Appointment not found",
            }

        # Cancel in both DB and calendar
        result = await cancel_appointment_with_calendar(
            db=db,
            calendar=calendar,
            appointment_id=str(appointment.id)
        )

        if result["success"]:
            # Update cancellation reason
            appointment.cancellation_reason = reason
            await db.commit()

            # Invalidate customer cache
            from app.services.redis_client import invalidate_customer_cache
            customer = await db.get(Customer, appointment.customer_id)
            if customer:
                await invalidate_customer_cache(customer.phone_number)

        return result

    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}", exc_info=True)
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to cancel appointment",
        }
```

**Add and commit**:
```bash
git add server/app/tools/crm_tools.py
git commit -m "feat: cancel Google Calendar events when cancelling appointments

- Use calendar_integration.cancel_appointment_with_calendar()
- Cancels both DB record AND calendar event
- Stores cancellation reason
- Invalidates customer cache"
```

#### STEP 5: Fix reschedule_appointment in crm_tools.py

**Current implementation** (line 696) - Only updates DB

**Update to**:
```python
async def reschedule_appointment(
    db: AsyncSession, appointment_id: int, new_datetime: str
) -> Dict[str, Any]:
    """
    Reschedule an appointment in both database AND Google Calendar.

    Args:
        db: Database session
        appointment_id: Appointment ID to reschedule
        new_datetime: New datetime (ISO format)

    Returns:
        Dict with reschedule result
    """
    try:
        from datetime import datetime
        from app.config import settings
        from app.services.calendar_service import CalendarService
        from app.services.calendar_integration import reschedule_appointment_with_calendar

        # Parse new datetime
        new_time = datetime.fromisoformat(new_datetime)

        # Initialize calendar service
        calendar = CalendarService(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            timezone_name=settings.TIMEZONE,
        )

        # Get appointment for cache invalidation
        appointment = await db.get(Appointment, appointment_id)
        if not appointment:
            return {
                "success": False,
                "error": f"Appointment {appointment_id} not found",
                "message": "Appointment not found",
            }

        # Reschedule in both DB and calendar
        result = await reschedule_appointment_with_calendar(
            db=db,
            calendar=calendar,
            appointment_id=str(appointment.id),
            new_start_time=new_time,
        )

        if result["success"]:
            # Invalidate customer cache
            from app.services.redis_client import invalidate_customer_cache
            customer = await db.get(Customer, appointment.customer_id)
            if customer:
                await invalidate_customer_cache(customer.phone_number)

        return result

    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}", exc_info=True)
        await db.rollback()
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to reschedule appointment",
        }
```

**Add and commit**:
```bash
git add server/app/tools/crm_tools.py
git commit -m "feat: update Google Calendar events when rescheduling appointments

- Use calendar_integration.reschedule_appointment_with_calendar()
- Updates both DB and calendar event times
- Invalidates customer cache"
```

#### STEP 6: Add Required Environment Variables

**Update** `.env.example`:
```bash
# Add to .env.example after existing Google Calendar variables
GOOGLE_CLIENT_ID=your_oauth2_client_id
GOOGLE_CLIENT_SECRET=your_oauth2_client_secret
GOOGLE_REFRESH_TOKEN=your_refresh_token
TIMEZONE=America/New_York
```

**Update** `server/app/config.py` to include:
```python
# Add to Settings class
GOOGLE_CLIENT_ID: str = Field(default="", description="Google OAuth2 Client ID")
GOOGLE_CLIENT_SECRET: str = Field(default="", description="Google OAuth2 Client Secret")
GOOGLE_REFRESH_TOKEN: str = Field(default="", description="Google OAuth2 Refresh Token")
TIMEZONE: str = Field(default="America/New_York", description="Timezone for appointments")
```

**Add and commit**:
```bash
git add .env.example server/app/config.py
git commit -m "config: add OAuth2 credentials and timezone settings for calendar integration

- Add GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
- Add TIMEZONE configuration
- Update .env.example with new required variables"
```

#### STEP 7: Update Tool Definitions for Better Calendar Context

**Update** `server/app/services/tool_definitions.py`:

```python
# Update get_available_slots schema (line 52)
{
    "type": "function",
    "function": {
        "name": "get_available_slots",
        "description": "Check Google Calendar for ACTUAL available appointment slots on a specific date. Returns real-time availability considering existing bookings. Business hours: Mon-Fri 9AM-5PM, Sat 9AM-3PM, Sun closed.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to check availability (format: YYYY-MM-DD, e.g., 2025-01-15)",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Minimum slot duration in minutes. Common values: 30 (oil change), 60 (brake service), 90 (complex repairs). Default: 30",
                    "default": 30,
                },
            },
            "required": ["date"],
        },
    },
},

# Update book_appointment schema (line 72)
{
    "type": "function",
    "function": {
        "name": "book_appointment",
        "description": "Book a service appointment for a customer. Creates appointment in database AND Google Calendar. Sends calendar invitation to customer email if available.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "Customer ID (obtained from lookup_customer result)",
                },
                "vehicle_id": {
                    "type": "integer",
                    "description": "Vehicle ID (obtained from lookup_customer result)",
                },
                "scheduled_at": {
                    "type": "string",
                    "description": "Appointment start time in ISO format (e.g., '2025-01-15T09:00:00'). MUST be within available slots from get_available_slots.",
                },
                "service_type": {
                    "type": "string",
                    "description": "Type of service to book (e.g., 'oil_change', 'brake_service', 'inspection', 'tire_rotation')",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes (default: 60). Should match duration used in get_available_slots.",
                    "default": 60,
                },
                "notes": {
                    "type": "string",
                    "description": "Any special notes or customer concerns (optional)",
                },
            },
            "required": ["customer_id", "vehicle_id", "scheduled_at", "service_type"],
        },
    },
},

# Update cancel_appointment schema (line 129)
{
    "type": "function",
    "function": {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment. Updates database status AND removes from Google Calendar. Customer will receive cancellation notification if they have email.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "integer",
                    "description": "Appointment ID to cancel (obtained from get_upcoming_appointments)",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for cancellation (helps with tracking and analytics)",
                    "enum": [
                        "schedule_conflict",
                        "got_service_elsewhere",
                        "vehicle_sold",
                        "issue_resolved",
                        "other",
                    ],
                },
            },
            "required": ["appointment_id"],
        },
    },
},

# Update reschedule_appointment schema (line 156)
{
    "type": "function",
    "function": {
        "name": "reschedule_appointment",
        "description": "Reschedule an existing appointment to a new time. Updates database AND Google Calendar event. Customer receives update notification. IMPORTANT: Check availability with get_available_slots before rescheduling.",
        "parameters": {
            "type": "object",
            "properties": {
                "appointment_id": {
                    "type": "integer",
                    "description": "Appointment ID to reschedule (obtained from get_upcoming_appointments)",
                },
                "new_datetime": {
                    "type": "string",
                    "description": "New appointment datetime in ISO format (e.g., '2025-01-16T14:00:00'). Should be from available slots.",
                },
            },
            "required": ["appointment_id", "new_datetime"],
        },
    },
},
```

**Add and commit**:
```bash
git add server/app/services/tool_definitions.py
git commit -m "docs: update tool schemas to reflect Google Calendar integration

- Clarify that get_available_slots checks REAL calendar
- Document that book/cancel/reschedule update both DB and calendar
- Add guidance about checking availability before booking/rescheduling
- Improve parameter descriptions for better LLM understanding"
```

#### STEP 8: Update System Prompts (Optional but Recommended)

**Update** `server/app/services/system_prompts.py` to mention calendar integration:

Add to the relevant section:
```python
"""
When scheduling appointments:
1. ALWAYS check availability first using get_available_slots
2. Only offer times that are actually available in our calendar
3. After booking, confirm the appointment and mention they'll receive a calendar invitation
4. If customer has email, let them know we sent a Google Calendar invite
5. For rescheduling, check new time availability before confirming the change
"""
```

**Add and commit**:
```bash
git add server/app/services/system_prompts.py
git commit -m "docs: add calendar integration guidance to system prompts

- Instruct LLM to always check availability first
- Mention calendar invitations to customers
- Guide proper booking workflow"
```

## Testing Instructions

After implementation, test these scenarios:

### Test 1: Check Availability
```python
# Should return REAL calendar slots, not mock data
result = await get_available_slots("2025-01-15", 30)
# Verify it queries Google Calendar freebusy API
```

### Test 2: Book Appointment
```python
# Should create both DB record and Google Calendar event
result = await book_appointment(
    db=db,
    customer_id=1,
    vehicle_id=1,
    scheduled_at="2025-01-15T10:00:00",
    service_type="oil_change",
    duration_minutes=60
)
# Check: calendar_event_id should be present
# Check: Google Calendar should show the event
```

### Test 3: Cancel Appointment
```python
# Should remove from both DB and calendar
result = await cancel_appointment(db, appointment_id=1, reason="schedule_conflict")
# Verify calendar event is deleted
```

### Test 4: Reschedule Appointment
```python
# Should update both DB and calendar event
result = await reschedule_appointment(db, appointment_id=1, new_datetime="2025-01-16T14:00:00")
# Verify calendar event time is updated
```

## Best Practices to Follow

1. **Always use asyncio.get_event_loop().run_in_executor()** for blocking Google API calls
2. **Proper timezone handling** - Use ZoneInfo, convert to UTC for API calls
3. **Comprehensive error handling** - Catch specific exceptions, log with context
4. **Git commits as you go** - Commit after each logical change with descriptive messages
5. **Invalidate caches** - Clear customer cache after appointment changes
6. **Transaction management** - Use db.rollback() on errors
7. **Logging** - Log at INFO for success, ERROR for failures with exc_info=True
8. **Return consistent structures** - All functions return {"success": bool, "data": dict, "message": str}

## Common Pitfalls to Avoid

1. ❌ **Don't** use service account authentication (we use OAuth2 refresh token)
2. ❌ **Don't** forget timezone conversion (local → UTC for API, UTC → local for display)
3. ❌ **Don't** make blocking API calls without executor
4. ❌ **Don't** forget to await async functions
5. ❌ **Don't** skip error handling - Google API can fail
6. ❌ **Don't** forget to commit changes regularly
7. ❌ **Don't** leave TODO comments - implement fully

## Success Criteria

✅ All mock implementations replaced with real Google Calendar API calls
✅ Appointments create actual calendar events
✅ Cancellations remove calendar events
✅ Rescheduling updates calendar events
✅ Proper OAuth2 authentication used throughout
✅ Timezone handling is correct
✅ All changes committed with descriptive messages
✅ No orphaned/unused code remains
✅ Error handling is comprehensive
✅ Logging provides good observability

## Official Google Calendar API Documentation (Context7)

### Freebusy Query API Structure

From Google Calendar API official docs, the freebusy endpoint structure:

```json
{
  "timeMin": "datetime",  // Required - Start of interval (RFC3339 format)
  "timeMax": "datetime",  // Required - End of interval (RFC3339 format)
  "timeZone": "string",   // Optional - Defaults to UTC
  "items": [
    {
      "id": "string"      // Required - Calendar ID (use "primary" for user's main calendar)
    }
  ]
}
```

**Response Structure:**
```json
{
  "kind": "calendar#freeBusy",
  "timeMin": "datetime",
  "timeMax": "datetime",
  "calendars": {
    "primary": {
      "busy": [
        {
          "start": "datetime",  // Inclusive start of busy period
          "end": "datetime"     // Exclusive end of busy period
        }
      ]
    }
  }
}
```

### OAuth2 Authentication for Calendar API

**Canonical Scopes** (from google-api-python-client docs):
- Full access: `https://www.googleapis.com/auth/calendar`
- Read-only: `https://www.googleapis.com/auth/calendar.readonly`

**Authentication Flow** (from google-auth-oauthlib):
```python
from google.oauth2.credentials import Credentials

# Initialize with refresh token (recommended for server-side apps)
creds = Credentials(
    token=None,                                    # Will be auto-refreshed
    refresh_token=self.refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=self.client_id,
    client_secret=self.client_secret,
    scopes=['https://www.googleapis.com/auth/calendar']
)

service = build('calendar', 'v3', credentials=creds)
```

**Important**: The credentials will automatically refresh the access_token when needed. No manual refresh logic required!

### Calendar Events Management

**Create Event** (POST /calendars/calendarId/events):
```python
event = {
    'summary': 'Event Title',
    'description': 'Event Description',
    'start': {
        'dateTime': '2025-01-15T09:00:00Z',  # ISO 8601 format in UTC
        'timeZone': 'UTC',
    },
    'end': {
        'dateTime': '2025-01-15T10:00:00Z',
        'timeZone': 'UTC',
    },
    'attendees': [
        {'email': 'attendee@example.com'}
    ]
}

event = service.events().insert(
    calendarId='primary',
    body=event,
    sendUpdates='all'  # Send email notifications to attendees
).execute()
```

**Update Event** (PATCH /calendars/calendarId/events/eventId):
```python
# Use PATCH for partial updates (more efficient)
updated_event = service.events().patch(
    calendarId='primary',
    eventId=event_id,
    body={
        'start': {'dateTime': new_start_time, 'timeZone': 'UTC'},
        'end': {'dateTime': new_end_time, 'timeZone': 'UTC'}
    },
    sendUpdates='all'
).execute()
```

**Delete Event** (DELETE /calendars/calendarId/events/eventId):
```python
service.events().delete(
    calendarId='primary',
    eventId=event_id,
    sendUpdates='all'  # Notify attendees of cancellation
).execute()
```

### Best Practices from Official Docs

1. **Always use `sendUpdates='all'`** when creating/updating/deleting events to notify attendees
2. **Use PATCH instead of PUT** for partial updates (saves bandwidth and quota)
3. **Handle 401 responses** - Credentials will auto-refresh, but catch the exception
4. **Timezone handling** - Always convert to UTC before sending to API
5. **Rate limiting** - Use exponential backoff for quota errors

## Resources

- Google Calendar API v3 Docs: https://developers.google.com/calendar/api/v3/reference
- OAuth2 for Calendar: https://developers.google.com/calendar/api/guides/auth
- Freebusy queries: https://developers.google.com/calendar/api/v3/reference/freebusy/query
- Python asyncio executor: https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor
- google-api-python-client docs: https://googleapis.github.io/google-api-python-client/

## Final Notes

This is a critical fix. The current implementation gives users false availability information and doesn't actually create calendar events. After your changes:

- ✅ Availability checks will reflect REAL calendar state
- ✅ Bookings will create ACTUAL calendar events
- ✅ Customers will receive calendar invitations
- ✅ The system will be production-ready for scheduling

**Remember**: Add and commit changes frequently as you go. Write clear commit messages. Test each function after implementing it. Good luck! 🚀
