"""Calendar tools for appointment scheduling using Google Calendar API."""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.config import settings


def get_calendar_service():
    """Initialize Google Calendar service."""
    credentials = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=credentials)


async def get_freebusy(
    start_date: datetime, end_date: datetime
) -> List[Dict[str, Any]]:
    """
    Get free/busy information for the service calendar.

    Args:
        start_date: Start of time range
        end_date: End of time range

    Returns:
        List of available time slots
    """
    service = get_calendar_service()

    body = {
        "timeMin": start_date.isoformat() + "Z",
        "timeMax": end_date.isoformat() + "Z",
        "items": [{"id": settings.GOOGLE_CALENDAR_ID}],
    }

    freebusy_result = service.freebusy().query(body=body).execute()
    busy_times = freebusy_result["calendars"][settings.GOOGLE_CALENDAR_ID].get(
        "busy", []
    )

    # Generate available slots (simplified logic)
    available_slots = []
    current_time = start_date

    while current_time < end_date:
        slot_end = current_time + timedelta(hours=1)

        # Check if slot overlaps with busy times
        is_available = True
        for busy in busy_times:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

            if current_time < busy_end and slot_end > busy_start:
                is_available = False
                break

        if is_available:
            available_slots.append(
                {
                    "start": current_time.isoformat(),
                    "end": slot_end.isoformat(),
                }
            )

        current_time += timedelta(hours=1)

    return available_slots


async def book_slot(
    start_time: datetime,
    duration_minutes: int,
    customer_name: str,
    service_type: str,
    customer_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Book an appointment slot in Google Calendar.

    Args:
        start_time: Appointment start time
        duration_minutes: Appointment duration
        customer_name: Customer name
        service_type: Type of service
        customer_email: Customer email for notifications

    Returns:
        Created event information
    """
    service = get_calendar_service()

    end_time = start_time + timedelta(minutes=duration_minutes)

    event = {
        "summary": f"{service_type} - {customer_name}",
        "description": f"Service appointment for {customer_name}",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "America/New_York",  # TODO: Make configurable
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "America/New_York",
        },
    }

    if customer_email:
        event["attendees"] = [{"email": customer_email}]

    created_event = (
        service.events()
        .insert(calendarId=settings.GOOGLE_CALENDAR_ID, body=event, sendUpdates="all")
        .execute()
    )

    return {
        "event_id": created_event["id"],
        "start": start_time.isoformat(),
        "end": end_time.isoformat(),
        "status": "confirmed",
    }


async def cancel_slot(event_id: str) -> Dict[str, Any]:
    """
    Cancel an appointment in Google Calendar.

    Args:
        event_id: Google Calendar event ID

    Returns:
        Cancellation status
    """
    service = get_calendar_service()

    service.events().delete(
        calendarId=settings.GOOGLE_CALENDAR_ID, eventId=event_id, sendUpdates="all"
    ).execute()

    return {"status": "cancelled", "event_id": event_id}
