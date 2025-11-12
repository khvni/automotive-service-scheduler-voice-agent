"""Webhook endpoints for external services."""

from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/twilio/status")
async def twilio_status_callback(request: Request):
    """
    Twilio status callback webhook.
    Receives call status updates (ringing, in-progress, completed, etc.)
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")

    logger.info(f"Call {call_sid} status: {call_status}")

    # Update call log in database
    # Send to monitoring/analytics

    return {"status": "received"}


@router.post("/calendar/notification")
async def google_calendar_notification(request: Request):
    """
    Google Calendar push notification webhook.
    Receives updates when calendar events change.
    """
    body = await request.json()
    logger.info(f"Calendar notification: {body}")

    # Process calendar change
    # Update appointment status if needed

    return {"status": "received"}
