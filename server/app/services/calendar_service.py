"""
Google Calendar Service for managing appointments.

This service provides async wrappers around the Google Calendar API for:
- Querying free/busy availability
- Creating calendar events
- Updating existing events
- Canceling/deleting events

Uses OAuth2 refresh token flow for authentication.

Features:
- Automatic retry with exponential backoff for transient errors
- Performance metrics tracking for all operations
- Health monitoring and alerting
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.utils.calendar_metrics import CalendarOperationMetrics, get_metrics_tracker
from app.utils.retry import with_retry
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class CalendarService:
    """
    Google Calendar integration service.

    This service uses refresh tokens for authentication and wraps all
    blocking Google API calls in async executors for compatibility with
    async/await patterns.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        timezone_name: str = "America/New_York",
        use_mock: bool = False,
    ):
        """
        Initialize Calendar Service.

        Args:
            client_id: Google OAuth2 client ID
            client_secret: Google OAuth2 client secret
            refresh_token: Google OAuth2 refresh token
            timezone_name: Timezone for appointment scheduling (default: America/New_York)
            use_mock: If True, use mock calendar data instead of real API (default: False)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.use_mock = use_mock

        try:
            self.timezone = ZoneInfo(timezone_name)
        except Exception as e:
            logger.warning(
                f"Invalid timezone {timezone_name}, falling back to America/New_York: {e}"
            )
            self.timezone = ZoneInfo("America/New_York")

        self._service = None

        if use_mock:
            logger.warning("⚠️  CalendarService initialized in MOCK mode - using fake calendar data")
        else:
            logger.info(f"CalendarService initialized with timezone: {timezone_name}")

    def get_calendar_service(self):
        """
        Build and return Google Calendar API service with OAuth2 credentials.

        This method creates credentials from the refresh token and builds
        the Calendar API service. The credentials will automatically refresh
        when needed.

        Returns:
            Google Calendar API service instance or None if using mock mode

        Raises:
            Exception: If credentials or service creation fails (only in non-mock mode)
        """
        if self.use_mock:
            return None  # Return None in mock mode, methods will handle this

        if self._service:
            return self._service

        try:
            logger.debug(f"Creating credentials with refresh token: {self.refresh_token[:10]}...")

            creds = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )

            logger.debug("Building calendar service...")
            self._service = build("calendar", "v3", credentials=creds)
            logger.info("Calendar service created successfully")

            return self._service

        except Exception as e:
            logger.error(f"Error creating calendar service: {e}", exc_info=True)
            logger.warning("⚠️  Falling back to MOCK calendar mode")
            self.use_mock = True
            return None

    async def get_free_availability(
        self, start_time: datetime, end_time: datetime, duration_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots within a date range.

        This method queries the Google Calendar freebusy API to find when
        the calendar is available. It then calculates free slots that are
        at least `duration_minutes` long, excluding lunch hours (12-1 PM).

        Includes automatic retry for transient errors and performance tracking.

        Args:
            start_time: Start of availability window (timezone-aware)
            end_time: End of availability window (timezone-aware)
            duration_minutes: Minimum slot duration in minutes (default: 30)

        Returns:
            List of available slots with 'start' and 'end' datetime objects
            Example: [
                {'start': datetime(...), 'end': datetime(...)},
                {'start': datetime(...), 'end': datetime(...)}
            ]

        Raises:
            Exception: If freebusy query fails after retries
        """
        # MOCK MODE: Return fake availability
        if self.use_mock:
            logger.warning("📅 MOCK: Returning fake calendar availability")
            return self._generate_mock_availability(start_time, end_time, duration_minutes)

        # Start metrics tracking
        metrics_tracker = get_metrics_tracker()
        metric = metrics_tracker.start_operation("freebusy_query")

        try:
            # Define the operation to retry
            async def _query_freebusy():
                service = self.get_calendar_service()

                # If service creation failed and fell back to mock mode
                if service is None:
                    logger.warning("📅 MOCK: Service unavailable, returning fake availability")
                    return self._generate_mock_availability(start_time, end_time, duration_minutes)

                # Ensure times are timezone-aware
                if start_time.tzinfo is None:
                    _start_time = start_time.replace(tzinfo=self.timezone)
                else:
                    _start_time = start_time

                if end_time.tzinfo is None:
                    _end_time = end_time.replace(tzinfo=self.timezone)
                else:
                    _end_time = end_time

                # Convert to UTC for API
                start_time_utc = _start_time.astimezone(timezone.utc)
                end_time_utc = _end_time.astimezone(timezone.utc)

                logger.info(f"Querying freebusy from {start_time_utc} to {end_time_utc}")

                body = {
                    "timeMin": start_time_utc.isoformat(),
                    "timeMax": end_time_utc.isoformat(),
                    "items": [{"id": "primary"}],
                }

                # Run blocking API call in executor
                freebusy_response = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: service.freebusy().query(body=body).execute()
                )

                logger.debug(f"Freebusy response: {freebusy_response}")

                # Process response to calculate free slots
                free_slots = self._process_freebusy_response(
                    freebusy_response, _start_time, _end_time, duration_minutes
                )

                logger.info(f"Found {len(free_slots)} free slots")
                return free_slots

            # Execute with retry logic (retries on transient errors like 500, 503)
            result = await with_retry(
                _query_freebusy,
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                operation_name="Calendar Freebusy Query",
            )

            metric.mark_success()
            metrics_tracker.record_operation(metric)
            return result

        except Exception as e:
            metric.mark_failure(e)
            metrics_tracker.record_operation(metric)
            logger.error(f"Error getting free availability after retries: {e}", exc_info=True)
            raise

    async def create_calendar_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new calendar event.

        Includes automatic retry for transient errors and performance tracking.

        Args:
            title: Event summary/title
            start_time: Event start time (timezone-aware)
            end_time: Event end time (timezone-aware)
            description: Event description/notes (default: "")
            attendees: List of attendee email addresses (default: None)

        Returns:
            Dictionary with event details:
            {
                'success': True,
                'event_id': 'google_event_id',
                'calendar_link': 'https://calendar.google.com/...',
                'message': 'Event created successfully'
            }

        Raises:
            Exception: If event creation fails
        """
        # MOCK MODE: Return fake success
        if self.use_mock:
            import uuid

            fake_id = f"mock_{uuid.uuid4().hex[:16]}"
            logger.warning(
                f"📅 MOCK: Pretending to create calendar event '{title}' (ID: {fake_id})"
            )
            return {
                "success": True,
                "event_id": fake_id,
                "calendar_link": f"https://calendar.google.com/calendar/event?eid={fake_id}",
                "message": f"MOCK: Event '{title}' created (fake)",
            }

        # Start metrics tracking
        metrics_tracker = get_metrics_tracker()
        metric = metrics_tracker.start_operation("create_event")

        try:

            async def _create_event():
                service = self.get_calendar_service()

                # Ensure times are timezone-aware
                _start_time = (
                    start_time.replace(tzinfo=self.timezone)
                    if start_time.tzinfo is None
                    else start_time
                )
                _end_time = (
                    end_time.replace(tzinfo=self.timezone) if end_time.tzinfo is None else end_time
                )

                # Convert to UTC for API
                start_time_utc = _start_time.astimezone(timezone.utc)
                end_time_utc = _end_time.astimezone(timezone.utc)

                logger.info(f"Creating calendar event: {title} at {start_time_utc}")

                event = {
                    "summary": title,
                    "description": description,
                    "start": {
                        "dateTime": start_time_utc.isoformat(),
                        "timeZone": "UTC",
                    },
                    "end": {
                        "dateTime": end_time_utc.isoformat(),
                        "timeZone": "UTC",
                    },
                }

                # Add attendees if provided
                if attendees:
                    event["attendees"] = [{"email": email} for email in attendees]
                    event["guestsCanModify"] = False
                    event["guestsCanInviteOthers"] = False

                # Run blocking API call in executor
                created_event = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: service.events()
                    .insert(calendarId="primary", body=event, sendUpdates="all")
                    .execute(),
                )

                logger.info(f"Event created successfully: {created_event['id']}")

                return {
                    "success": True,
                    "event_id": created_event.get("id"),
                    "calendar_link": created_event.get("htmlLink"),
                    "message": f"Event '{title}' scheduled successfully",
                }

            # Execute with retry logic
            result = await with_retry(
                _create_event,
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                operation_name="Calendar Event Creation",
            )

            metric.mark_success()
            metrics_tracker.record_operation(metric)
            return result

        except Exception as e:
            metric.mark_failure(e)
            metrics_tracker.record_operation(metric)
            logger.error(f"Error creating calendar event after retries: {e}", exc_info=True)
            return {
                "success": False,
                "event_id": None,
                "calendar_link": None,
                "message": f"Failed to create event: {str(e)}",
            }

    async def update_calendar_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing calendar event.

        Only provided fields will be updated. Fields set to None will
        remain unchanged.

        Includes automatic retry for transient errors and performance tracking.

        Args:
            event_id: Google Calendar event ID
            title: New event title (optional)
            start_time: New start time (optional)
            end_time: New end time (optional)
            description: New description (optional)
            attendees: New attendee list (optional)

        Returns:
            Dictionary with update result:
            {
                'success': True,
                'event_id': 'google_event_id',
                'calendar_link': 'https://calendar.google.com/...',
                'message': 'Event updated successfully'
            }

        Raises:
            Exception: If event update fails
        """
        # MOCK MODE: Return fake success
        if self.use_mock:
            logger.warning(f"📅 MOCK: Pretending to update calendar event {event_id}")
            return {
                "success": True,
                "event_id": event_id,
                "calendar_link": f"https://calendar.google.com/calendar/event?eid={event_id}",
                "message": "MOCK: Event updated (fake)",
            }

        # Start metrics tracking
        metrics_tracker = get_metrics_tracker()
        metric = metrics_tracker.start_operation("update_event")

        try:

            async def _update_event():
                service = self.get_calendar_service()

                logger.info(f"Updating calendar event: {event_id}")

                # Get existing event
                event = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: service.events().get(calendarId="primary", eventId=event_id).execute(),
                )

                # Update provided fields
                if title:
                    event["summary"] = title
                if description is not None:  # Allow empty string
                    event["description"] = description

                # Update time if both start and end provided
                if start_time and end_time:
                    # Ensure times are timezone-aware
                    _start_time = (
                        start_time.replace(tzinfo=self.timezone)
                        if start_time.tzinfo is None
                        else start_time
                    )
                    _end_time = (
                        end_time.replace(tzinfo=self.timezone)
                        if end_time.tzinfo is None
                        else end_time
                    )

                    # Convert to UTC for API
                    start_time_utc = _start_time.astimezone(timezone.utc)
                    end_time_utc = _end_time.astimezone(timezone.utc)

                    event["start"] = {
                        "dateTime": start_time_utc.isoformat(),
                        "timeZone": "UTC",
                    }
                    event["end"] = {
                        "dateTime": end_time_utc.isoformat(),
                        "timeZone": "UTC",
                    }

                # Update attendees if provided
                if attendees is not None:
                    event["attendees"] = [{"email": email} for email in attendees]

                # Run blocking API call in executor
                updated_event = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: service.events()
                    .update(calendarId="primary", eventId=event_id, body=event, sendUpdates="all")
                    .execute(),
                )

                logger.info(f"Event updated successfully: {event_id}")

                return {
                    "success": True,
                    "event_id": updated_event.get("id"),
                    "calendar_link": updated_event.get("htmlLink"),
                    "message": "Event updated successfully",
                }

            # Execute with retry logic
            result = await with_retry(
                _update_event,
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                operation_name="Calendar Event Update",
            )

            metric.mark_success()
            metrics_tracker.record_operation(metric)
            return result

        except Exception as e:
            metric.mark_failure(e)
            metrics_tracker.record_operation(metric)
            logger.error(f"Error updating calendar event after retries: {e}", exc_info=True)
            return {
                "success": False,
                "event_id": event_id,
                "calendar_link": None,
                "message": f"Failed to update event: {str(e)}",
            }

    async def cancel_calendar_event(self, event_id: str) -> Dict[str, bool]:
        """
        Cancel (delete) a calendar event.

        Includes automatic retry for transient errors and performance tracking.

        Args:
            event_id: Google Calendar event ID

        Returns:
            Dictionary with cancellation result:
            {
                'success': True,
                'message': 'Event cancelled successfully'
            }

        Raises:
            Exception: If event cancellation fails
        """
        # MOCK MODE: Return fake success
        if self.use_mock:
            logger.warning(f"📅 MOCK: Pretending to cancel calendar event {event_id}")
            return {"success": True, "message": "MOCK: Event cancelled (fake)"}

        # Start metrics tracking
        metrics_tracker = get_metrics_tracker()
        metric = metrics_tracker.start_operation("delete_event")

        try:

            async def _cancel_event():
                service = self.get_calendar_service()

                logger.info(f"Cancelling calendar event: {event_id}")

                # Run blocking API call in executor
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: service.events()
                    .delete(calendarId="primary", eventId=event_id, sendUpdates="all")
                    .execute(),
                )

                logger.info(f"Event cancelled successfully: {event_id}")

                return {"success": True, "message": "Event cancelled successfully"}

            # Execute with retry logic
            result = await with_retry(
                _cancel_event,
                max_retries=3,
                backoff_factor=2.0,
                initial_delay=1.0,
                operation_name="Calendar Event Cancellation",
            )

            metric.mark_success()
            metrics_tracker.record_operation(metric)
            return result

        except Exception as e:
            metric.mark_failure(e)
            metrics_tracker.record_operation(metric)
            logger.error(f"Error cancelling calendar event after retries: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to cancel event: {str(e)}"}

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific calendar event.

        Args:
            event_id: Google Calendar event ID

        Returns:
            Event details dictionary or None if not found

        Raises:
            Exception: If event retrieval fails
        """
        try:
            service = self.get_calendar_service()

            logger.info(f"Getting calendar event: {event_id}")

            # Run blocking API call in executor
            event = await asyncio.get_event_loop().run_in_executor(
                None, lambda: service.events().get(calendarId="primary", eventId=event_id).execute()
            )

            logger.info(f"Event retrieved successfully: {event_id}")
            return event

        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Event not found: {event_id}")
                return None
            logger.error(f"Google Calendar API error in get_event: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting calendar event: {e}", exc_info=True)
            raise

    def _process_freebusy_response(
        self,
        freebusy_response: Dict[str, Any],
        start_time: datetime,
        end_time: datetime,
        duration_minutes: int,
    ) -> List[Dict[str, datetime]]:
        """
        Calculate free slots from Google Calendar freebusy response.

        This method:
        1. Extracts busy periods from the API response
        2. Calculates gaps between busy periods
        3. Filters out slots shorter than duration_minutes
        4. Excludes lunch hour (12-1 PM)
        5. Returns list of available time slots

        Args:
            freebusy_response: Response from Google Calendar freebusy API
            start_time: Start of query window
            end_time: End of query window
            duration_minutes: Minimum slot duration

        Returns:
            List of free slots with start/end times
        """
        try:
            busy_periods = freebusy_response.get("calendars", {}).get("primary", {}).get("busy", [])
            logger.debug(f"Found {len(busy_periods)} busy periods")

            free_slots = []
            current_time = start_time

            # Process each busy period
            for busy in busy_periods:
                # Parse busy period times
                busy_start_str = busy["start"]
                busy_end_str = busy["end"]

                # Handle both Z and +00:00 timezone formats
                busy_start = datetime.fromisoformat(busy_start_str.replace("Z", "+00:00"))
                busy_end = datetime.fromisoformat(busy_end_str.replace("Z", "+00:00"))

                # Convert to local timezone
                busy_start = busy_start.astimezone(self.timezone)
                busy_end = busy_end.astimezone(self.timezone)

                # Check if there's a free slot before this busy period
                if current_time < busy_start:
                    slot_duration = (busy_start - current_time).total_seconds() / 60

                    if slot_duration >= duration_minutes:
                        # Check if slot overlaps with lunch (12-1 PM)
                        free_slots.extend(
                            self._split_slot_around_lunch(
                                current_time, busy_start, duration_minutes
                            )
                        )

                # Move current time to end of busy period
                current_time = max(current_time, busy_end)

            # Check for free slot after last busy period
            if current_time < end_time:
                slot_duration = (end_time - current_time).total_seconds() / 60

                if slot_duration >= duration_minutes:
                    free_slots.extend(
                        self._split_slot_around_lunch(current_time, end_time, duration_minutes)
                    )

            logger.debug(f"Calculated {len(free_slots)} free slots")
            return free_slots

        except Exception as e:
            logger.error(f"Error processing freebusy response: {e}", exc_info=True)
            return []

    def _split_slot_around_lunch(
        self, slot_start: datetime, slot_end: datetime, duration_minutes: int
    ) -> List[Dict[str, datetime]]:
        """
        Split a free slot around lunch hour (12-1 PM).

        Args:
            slot_start: Start of free slot
            slot_end: End of free slot
            duration_minutes: Minimum slot duration

        Returns:
            List of free slots (may be split if overlapping lunch)
        """
        slots = []

        # Define lunch hour for this day (12-1 PM)
        lunch_start = slot_start.replace(hour=12, minute=0, second=0, microsecond=0)
        lunch_end = slot_start.replace(hour=13, minute=0, second=0, microsecond=0)

        # Check if slot overlaps with lunch
        if slot_start < lunch_end and slot_end > lunch_start:
            # Split around lunch

            # Morning slot (before lunch)
            if slot_start < lunch_start:
                morning_duration = (lunch_start - slot_start).total_seconds() / 60
                if morning_duration >= duration_minutes:
                    slots.append({"start": slot_start, "end": lunch_start})

            # Afternoon slot (after lunch)
            if slot_end > lunch_end:
                afternoon_duration = (slot_end - lunch_end).total_seconds() / 60
                if afternoon_duration >= duration_minutes:
                    slots.append({"start": lunch_end, "end": slot_end})
        else:
            # No lunch overlap, add entire slot
            slots.append({"start": slot_start, "end": slot_end})

        return slots

    def _generate_mock_availability(
        self, start_time: datetime, end_time: datetime, duration_minutes: int
    ) -> List[Dict[str, datetime]]:
        """
        Generate mock calendar availability for testing when API is unavailable.

        Args:
            start_time: Start of availability window
            end_time: End of availability window
            duration_minutes: Minimum slot duration

        Returns:
            List of fake available slots
        """
        # Ensure times are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=self.timezone)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=self.timezone)

        # Generate slots every 30 minutes during business hours
        slots = []
        current = start_time

        # Set to business hours (9 AM - 5 PM)
        business_start = current.replace(hour=9, minute=0, second=0, microsecond=0)
        business_end = current.replace(hour=17, minute=0, second=0, microsecond=0)

        current = max(current, business_start)
        end = min(end_time, business_end)

        while current < end:
            slot_end = current + timedelta(minutes=duration_minutes)
            if slot_end <= end:
                # Exclude lunch hour (12-1 PM)
                lunch_start = current.replace(hour=12, minute=0)
                lunch_end = current.replace(hour=13, minute=0)

                if not (current < lunch_end and slot_end > lunch_start):
                    slots.append({"start": current, "end": slot_end})

            current += timedelta(minutes=30)

        logger.info(f"📅 MOCK: Generated {len(slots)} fake availability slots")
        return slots
