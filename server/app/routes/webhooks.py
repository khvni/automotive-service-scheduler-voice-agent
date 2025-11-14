"""Webhook endpoints for external services."""

import logging

from app.config import settings
from fastapi import APIRouter, Form, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import Connect, VoiceResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/incoming-call")
async def handle_incoming_call(
    request: Request, From: str = Form(...), To: str = Form(...), CallSid: str = Form(...)
):
    """
    Twilio webhook for incoming calls.
    Returns TwiML with <Connect><Stream> to WebSocket.

    This endpoint is called by Twilio when a call comes in to the configured number.
    It generates TwiML that:
    1. Greets the caller (optional)
    2. Connects to WebSocket for real-time AI conversation

    Args:
        From: Caller's phone number (E.164 format)
        To: Twilio phone number being called
        CallSid: Unique identifier for the call

    Returns:
        TwiML XML response with Stream connection
    """
    logger.info(f"Incoming call - From: {From}, To: {To}, CallSid: {CallSid}")

    response = VoiceResponse()

    # Optional: Greet caller before connecting
    # Uncomment to add initial greeting
    # response.say(
    #     "Thank you for calling Otto's Auto. "
    #     "Please wait while we connect you to our AI assistant.",
    #     voice="Polly.Joanna"
    # )
    # response.pause(length=1)

    # Connect to WebSocket with call parameters
    connect = Connect()

    # WebSocket URL using BASE_URL from settings
    ws_url = f"wss://{settings.BASE_URL.replace('https://', '').replace('http://', '')}/api/v1/voice/media-stream"

    stream = connect.stream(url=ws_url)

    # Pass caller info as parameters (accessible in WebSocket handler)
    stream.parameter(name="From", value=From)
    stream.parameter(name="To", value=To)
    stream.parameter(name="CallSid", value=CallSid)

    response.append(connect)

    logger.debug(f"Generated TwiML for call {CallSid}")
    return Response(content=str(response), media_type="application/xml")


@router.post("/call-status")
async def handle_call_status(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: str = Form(None),
    From: str = Form(None),
    To: str = Form(None),
):
    """
    Twilio call status callback webhook.
    Receives status updates for call lifecycle events.

    Call statuses:
    - queued: Call is queued
    - ringing: Call is ringing
    - in-progress: Call answered
    - completed: Call finished normally
    - busy: Callee was busy
    - no-answer: No one answered
    - canceled: Call canceled before connection
    - failed: Call failed

    Args:
        CallSid: Unique call identifier
        CallStatus: Current call status
        CallDuration: Duration in seconds (for completed calls)
        From: Caller's phone number
        To: Called phone number

    Returns:
        JSON acknowledgment
    """
    logger.info(
        f"Call status update - CallSid: {CallSid}, Status: {CallStatus}, Duration: {CallDuration}s"
    )

    # TODO: Store call status in database for analytics
    # TODO: Send to monitoring/alerting system

    return {"status": "received"}


@router.post("/status")
async def status_callback(request: Request):
    """
    Twilio status callback webhook.
    Receives call status updates (initiated, ringing, in-progress, completed, etc.)

    This is the endpoint used by outbound calls made via test_voice_calls.py
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    call_duration = form_data.get("CallDuration")

    logger.info(f"Call status update - SID: {call_sid}, Status: {call_status}, Duration: {call_duration}s")

    # Update call log in database
    # Send to monitoring/analytics

    return {"status": "received"}


@router.post("/twilio/status")
async def twilio_status_callback(request: Request):
    """
    Alternative Twilio status callback webhook.
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
