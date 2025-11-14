"""
Voice call handling routes and WebSocket endpoints.

This module implements the main WebSocket handler for Twilio Media Streams,
orchestrating STT, LLM, TTS, and tool execution for real-time voice conversations.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.database import get_db
from app.services.deepgram_stt import DeepgramSTTService
from app.services.deepgram_tts import DeepgramTTSService
from app.services.openai_service import OpenAIService
from app.services.redis_client import get_session, set_session, update_session
from app.services.tool_definitions import TOOL_SCHEMAS
from app.services.tool_router import ToolRouter
from app.utils.audio_buffer import AudioBuffer
from app.utils.performance_metrics import PerformanceMetrics
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)

router = APIRouter()

# Constants (removed BARGE_IN_WORD_THRESHOLD - now triggers on ANY interim result for instant interruption)


# System prompt for the AI assistant
SYSTEM_PROMPT = """You are Sophie, a friendly and professional receptionist at Otto's Auto,
a full-service automotive repair shop.

Your role:
- Help customers schedule service appointments
- Answer questions about services, hours, and pricing
- Look up customer information and service history
- Provide a warm, efficient customer service experience

STRICT BOUNDARIES:
- You ONLY discuss automotive service topics (vehicle repairs, maintenance, appointments, pricing, hours)
- You are NOT a general assistant - you are specialized in automotive service ONLY
- If asked about ANY non-automotive topic (technology, politics, cybersecurity, news, etc.), politely decline:
  "I'm specialized in automotive service only. How can I help with your vehicle today?"
- NEVER provide information outside automotive service, even if you know the answer

FORMATTING RULES (CRITICAL):
- Speak naturally and conversationally as if on a phone call
- NEVER use markdown, asterisks (*), bullet points, or formatting symbols
- NEVER read punctuation marks aloud (don't say "asterisk" or "dash")
- NEVER use ChatGPT-style formatted lists or structured responses
- Keep responses concise and phone-appropriate (1-3 sentences per turn)
- Sound human, not like a text chatbot

Key guidelines:
- Be conversational and natural (not robotic)
- Ask one question at a time
- Listen carefully before offering solutions
- Confirm important details (name, date, time, vehicle)
- Use customer's name when you know it
- Be efficient but friendly (target 2-3 minutes for scheduling)

Business hours:
- Monday-Friday: 8 AM - 6 PM
- Saturday: 9 AM - 3 PM
- Sunday: Closed

Common services:
- Oil changes ($40-$80)
- Brake service
- Tire rotation
- State inspection
- Engine diagnostics
- General maintenance

When you don't know something:
- For complex diagnostics: "We'll need to inspect your vehicle to give an accurate assessment"
- For exact pricing: "Typical range is $X-Y, but final price depends on your specific vehicle"
- For policy exceptions: "Let me connect you with a manager who can help with that"

Customer lookup guidelines:
- If you can't find a customer by name, clearly state: "I don't see [name] in our system. Could you provide your phone number so I can look you up?"
- If a customer has no vehicles on file, state: "I see your account, but I don't have any vehicles listed. What vehicle would you like to bring in?"
- NEVER loop with repeated apologies - if a lookup fails twice, ask for different information
- Move the conversation forward - don't get stuck retrying the same failed approach

Remember: You're helpful, knowledgeable, and focused on getting customers scheduled efficiently.
Stay strictly within automotive service topics and speak naturally for phone conversations."""


def create_tool_handler(router: ToolRouter, tool_name: str):
    """
    Create a tool handler function for OpenAI service.

    This wrapper ensures each tool has its own closure with the correct tool_name.

    Args:
        router: ToolRouter instance
        tool_name: Name of the tool to execute

    Returns:
        Async function that executes the tool
    """

    async def handler(**kwargs) -> Dict[str, Any]:
        logger.info(f"Executing tool: {tool_name}")
        result = await router.execute(tool_name, **kwargs)
        return result

    return handler


@router.post("/incoming")
async def handle_incoming_call(request: Request):
    """
    Twilio webhook for incoming calls (both inbound and outbound).
    Returns TwiML to establish WebSocket connection.

    Query Parameters:
        appointment_id (optional): ID of appointment for contextualized outbound greetings
    """
    # Get form data from Twilio webhook
    form_data = await request.form()
    call_direction = form_data.get("Direction", "inbound")  # "inbound" or "outbound-api"
    caller_number = form_data.get("From", "")

    # Get optional appointment_id from query parameters
    appointment_id = request.query_params.get("appointment_id", "")

    # Strip protocol from BASE_URL to construct proper WebSocket URL
    ws_url = f"wss://{settings.BASE_URL.replace('https://', '').replace('http://', '')}/api/v1/voice/media-stream"

    # Determine if this is an outbound call
    is_outbound = "outbound" in call_direction.lower()

    # Only say "please wait" for inbound calls (outbound will get immediate greeting from agent)
    if is_outbound:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="is_outbound" value="true"/>
            <Parameter name="direction" value="{call_direction}"/>
            <Parameter name="From" value="{caller_number}"/>
            <Parameter name="appointment_id" value="{appointment_id}"/>
        </Stream>
    </Connect>
</Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Google.en-US-Chirp3-HD-Aoede">
        Please wait while we connect you to our AI assistant.
    </Say>
    <Pause length="1"/>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="is_outbound" value="false"/>
            <Parameter name="direction" value="{call_direction}"/>
            <Parameter name="From" value="{caller_number}"/>
        </Stream>
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/incoming-reminder")
async def handle_incoming_reminder(request: Request):
    """
    Twilio webhook for outbound reminder calls.
    Returns TwiML to establish WebSocket connection with reminder context.

    This endpoint is called by the worker job when making outbound reminder calls.
    The WebSocket handler will detect the reminder context and use appropriate prompts.

    Query Parameters:
        appointment_id: Optional appointment ID for contextualized reminder greeting
    """
    ws_url = f"wss://{settings.BASE_URL.replace('https://', '').replace('http://', '')}/api/v1/voice/media-stream"

    # Check if appointment_id provided in query params
    appointment_id = request.query_params.get("appointment_id")

    # Build TwiML with parameters
    parameters = '<Parameter name="call_type" value="outbound_reminder"/>'
    if appointment_id:
        parameters += f'\n            <Parameter name="appointment_id" value="{appointment_id}"/>'

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            {parameters}
        </Stream>
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """
    Main WebSocket handler for Twilio Media Streams.

    Architecture:
        Twilio WebSocket ↔ FastAPI WebSocket Handler
                                ↓
                    ┌───────────┴───────────┐
                    ↓                       ↓
              Deepgram STT              Deepgram TTS
                    ↓                       ↑
              Transcript Queue         Audio Queue
                    ↓                       ↑
              OpenAI GPT-4o  ←→  Tool Execution
                    ↓                       ↑
              Response Stream ──────────────┘

    Flow:
        1. Twilio connects and sends audio (mulaw @ 8kHz)
        2. Audio → Deepgram STT → transcript queue
        3. Final transcripts → OpenAI GPT-4o → response text + tool calls
        4. Response text → Deepgram TTS → audio queue
        5. Audio → Twilio → caller

    Barge-in:
        - STT interim results while TTS speaking = interruption detected
        - Send "clear" event to Twilio to stop audio playback
        - Clear TTS audio queue
        - Process new user input immediately

    Error Handling:
        - WebSocket disconnects (graceful cleanup)
        - Service failures (STT, TTS, OpenAI) with logging
        - Tool execution errors (returned to LLM for handling)
        - Redis failures (non-critical, log and continue)
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    # Session state
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    caller_phone: Optional[str] = None
    is_speaking = False

    # Mark-based audio playback tracking (call-gpt pattern)
    # Tracks which audio chunks are actively playing on Twilio
    marks: List[str] = []

    # Silence detection tracking
    last_user_input_time: float = time.time()
    silence_prompted: bool = False

    # Services (initialized in try block)
    stt: Optional[DeepgramSTTService] = None
    tts: Optional[DeepgramTTSService] = None
    openai: Optional[OpenAIService] = None
    db: Optional[AsyncSession] = None

    # Utilities
    audio_buffer: Optional[AudioBuffer] = None
    metrics: Optional[PerformanceMetrics] = None

    try:
        # Initialize services
        logger.info("Initializing services (STT, TTS, OpenAI)")

        stt = DeepgramSTTService(settings.DEEPGRAM_API_KEY)
        tts = DeepgramTTSService(settings.DEEPGRAM_API_KEY)
        openai = OpenAIService(
            api_key=settings.OPENAI_API_KEY, model="gpt-4o", temperature=0.8, max_tokens=1000
        )

        # Initialize utilities
        audio_buffer = AudioBuffer(buffer_size=3200)  # Optimal for mulaw @ 8kHz
        metrics = PerformanceMetrics()

        # Connect to STT and TTS
        await stt.connect()
        await tts.connect()
        logger.info("STT and TTS connected successfully")

        # Get database session for tool execution
        # Note: Using async context manager to ensure proper cleanup
        db_gen = get_db()
        db = await db_gen.__anext__()

        # Initialize tool router and register tools with OpenAI
        logger.info("Registering tools with OpenAI service")
        tool_router = ToolRouter(db)

        for tool_schema in TOOL_SCHEMAS:
            tool_name = tool_schema["function"]["name"]
            openai.register_tool(
                name=tool_name,
                description=tool_schema["function"]["description"],
                parameters=tool_schema["function"]["parameters"],
                handler=create_tool_handler(tool_router, tool_name),
            )

        logger.info(f"Registered {len(TOOL_SCHEMAS)} tools")

        # Set system prompt
        openai.set_system_prompt(SYSTEM_PROMPT)

        # Two concurrent tasks for bidirectional streaming
        async def receive_from_twilio():
            """
            Receive audio and events from Twilio Media Stream.

            Handles:
            - start: Initialize session, set up state
            - media: Audio chunks (base64 mulaw) → send to STT
            - mark: Acknowledgment markers for synchronization
            - stop: Call ended, cleanup
            """
            nonlocal call_sid, stream_sid, caller_phone

            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    event = data.get("event")

                    if event == "connected":
                        logger.info("Twilio Media Stream connected")

                    elif event == "start":
                        call_sid = data["start"]["callSid"]
                        stream_sid = data["start"]["streamSid"]

                        # Extract caller phone from customParameters or start data
                        custom_params = data["start"].get("customParameters", {})
                        caller_phone = custom_params.get("From") or data["start"].get("from")

                        logger.info(
                            f"Call started - SID: {call_sid}, Stream: {stream_sid}, From: {caller_phone}"
                        )

                        # Initialize session in Redis
                        await set_session(
                            call_sid,
                            {
                                "stream_sid": stream_sid,
                                "caller_phone": caller_phone,
                                "started_at": datetime.now(timezone.utc).isoformat(),
                                "conversation_history": [],
                            },
                        )

                        # Personalize system prompt if customer exists
                        if caller_phone:
                            try:
                                from app.tools.crm_tools import lookup_customer

                                customer = await lookup_customer(db, caller_phone)

                                if customer:
                                    # Enhance prompt with customer context
                                    personalized_prompt = SYSTEM_PROMPT + f"\n\nCUSTOMER CONTEXT:\n"
                                    personalized_prompt += f"- Name: {customer['first_name']} {customer['last_name']}\n"
                                    personalized_prompt += f"- Customer since: {customer.get('customer_since', 'Unknown')}\n"

                                    if customer.get("last_service_date"):
                                        personalized_prompt += (
                                            f"- Last service: {customer['last_service_date']}\n"
                                        )

                                    if customer.get("vehicles"):
                                        vehicles = [
                                            f"{v['year']} {v['make']} {v['model']}"
                                            for v in customer["vehicles"]
                                        ]
                                        personalized_prompt += (
                                            f"- Vehicles: {', '.join(vehicles)}\n"
                                        )

                                    personalized_prompt += (
                                        f"\nGreet them by name and provide personalized service!"
                                    )
                                    openai.set_system_prompt(personalized_prompt)
                                    logger.info(
                                        f"Personalized prompt for customer: {customer['first_name']}"
                                    )
                            except Exception as e:
                                logger.warning(f"Could not personalize prompt: {e}")

                        # Send initial greeting for ALL calls (both inbound and outbound)
                        # Proactive greeting improves UX and reduces awkward silence
                        call_direction = custom_params.get("direction", "inbound")

                        if call_direction == "outbound" or custom_params.get("is_outbound") == "true":
                            # OUTBOUND CALL - Appointment-specific greeting
                            logger.info("Outbound call detected - sending initial greeting")

                            try:
                                # Check if appointment_id was provided for contextualized greeting
                                appointment_id = custom_params.get("appointment_id", "")
                                initial_message = "Hi, this is Sophie from Otto's Auto. Is this a good time to talk?"

                                if appointment_id:
                                    try:
                                        # Validate appointment_id is a valid integer
                                        try:
                                            appt_id = int(appointment_id)
                                            if appt_id <= 0:
                                                raise ValueError("Appointment ID must be positive")
                                        except (ValueError, TypeError) as e:
                                            logger.warning(f"Invalid appointment_id '{appointment_id}': {e}, using generic greeting")
                                            raise  # Re-raise to skip to generic greeting

                                        # Fetch appointment details for contextualized greeting
                                        from app.tools.crm_tools import get_appointment_details
                                        from sqlalchemy import select
                                        from app.models.appointment import Appointment
                                        from app.models.vehicle import Vehicle
                                        from app.models.customer import Customer

                                        # Query appointment with vehicle and customer
                                        result = await db.execute(
                                            select(Appointment, Vehicle, Customer)
                                            .join(Vehicle, Appointment.vehicle_id == Vehicle.id)
                                            .join(Customer, Appointment.customer_id == Customer.id)
                                            .where(Appointment.id == appt_id)
                                        )
                                        row = result.first()

                                        if row:
                                            appointment, vehicle, customer = row

                                            # Format scheduled date/time
                                            appt_date = appointment.scheduled_at.strftime("%A, %B %d")
                                            appt_time = appointment.scheduled_at.strftime("%I:%M %p").lstrip("0")

                                            # Create contextualized greeting
                                            initial_message = (
                                                f"Hi {customer.first_name}, this is Sophie from Otto's Auto. "
                                                f"I'm calling about your upcoming {appointment.service_type.value.replace('_', ' ')} "
                                                f"appointment for your {vehicle.year} {vehicle.make} {vehicle.model} "
                                                f"scheduled for {appt_date} at {appt_time}. Is this a good time to talk?"
                                            )
                                            logger.info(f"Generated contextualized greeting for appointment {appt_id}")
                                        else:
                                            logger.warning(f"Appointment {appt_id} not found, using generic greeting")
                                    except Exception as e:
                                        logger.warning(f"Could not fetch appointment details: {e}, using generic greeting")

                                # Add initial greeting to conversation history so context is maintained
                                openai.add_assistant_message(initial_message)

                                # Send through TTS
                                async for audio_chunk in tts.text_to_speech(initial_message):
                                    if audio_chunk:
                                        # Encode to base64 for Twilio
                                        audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")

                                        # Send to Twilio with mark tracking
                                        await websocket.send_text(
                                            json.dumps({
                                                "event": "media",
                                                "streamSid": stream_sid,
                                                "media": {"payload": audio_b64},
                                            })
                                        )

                                        # Send mark event immediately after media (call-gpt pattern)
                                        mark_label = str(uuid.uuid4())
                                        await websocket.send_text(
                                            json.dumps({
                                                "event": "mark",
                                                "streamSid": stream_sid,
                                                "mark": {"name": mark_label},
                                            })
                                        )
                                        marks.append(mark_label)

                                logger.info("Initial greeting sent successfully")
                            except Exception as e:
                                logger.error(f"Failed to send initial greeting: {e}", exc_info=True)
                        else:
                            # INBOUND CALL - Generic friendly greeting
                            logger.info("Inbound call detected - sending proactive greeting")

                            try:
                                # Personalize if we have customer info, otherwise generic
                                if caller_phone:
                                    try:
                                        from app.tools.crm_tools import lookup_customer
                                        customer = await lookup_customer(db, caller_phone)
                                        if customer:
                                            initial_message = f"Hello {customer['first_name']}! This is Sophie from Otto's Auto. How can I help you today?"
                                        else:
                                            initial_message = "Hello! This is Sophie from Otto's Auto. How can I help you today?"
                                    except:
                                        initial_message = "Hello! This is Sophie from Otto's Auto. How can I help you today?"
                                else:
                                    initial_message = "Hello! This is Sophie from Otto's Auto. How can I help you today?"

                                # Add initial greeting to conversation history so context is maintained
                                openai.add_assistant_message(initial_message)

                                # Send through TTS
                                async for audio_chunk in tts.text_to_speech(initial_message):
                                    if audio_chunk:
                                        # Encode to base64 for Twilio
                                        audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")

                                        # Send to Twilio with mark tracking
                                        await websocket.send_text(
                                            json.dumps({
                                                "event": "media",
                                                "streamSid": stream_sid,
                                                "media": {"payload": audio_b64},
                                            })
                                        )

                                        # Send mark event immediately after media (call-gpt pattern)
                                        mark_label = str(uuid.uuid4())
                                        await websocket.send_text(
                                            json.dumps({
                                                "event": "mark",
                                                "streamSid": stream_sid,
                                                "mark": {"name": mark_label},
                                            })
                                        )
                                        marks.append(mark_label)

                                logger.info("Inbound proactive greeting sent successfully")
                            except Exception as e:
                                logger.error(f"Failed to send inbound greeting: {e}", exc_info=True)

                    elif event == "media":
                        # Decode audio and send to STT
                        audio_payload = data["media"]["payload"]
                        audio_bytes = base64.b64decode(audio_payload)

                        # Validate audio before buffering
                        if audio_bytes and len(audio_bytes) > 0:
                            # Add to buffer and get complete chunks
                            buffered_chunks = audio_buffer.add(audio_bytes)

                            # Send buffered chunks to STT
                            for chunk in buffered_chunks:
                                await stt.send_audio(chunk)
                        else:
                            logger.debug("Skipped empty audio packet")

                    elif event == "mark":
                        # Mark acknowledgment - audio chunk completed playback
                        mark_name = data["mark"].get("name")
                        if mark_name in marks:
                            marks.remove(mark_name)
                            logger.debug(f"Mark completed and removed: {mark_name} ({len(marks)} remaining)")
                        else:
                            logger.debug(f"Mark received but not tracked: {mark_name}")

                    elif event == "stop":
                        logger.info("Twilio Media Stream stop event received")
                        break

            except WebSocketDisconnect:
                logger.info("Twilio disconnected (receive task)")
            except Exception as e:
                logger.error(
                    f"Error in receive_from_twilio: {e}",
                    exc_info=True,
                    extra={
                        "call_sid": call_sid,
                        "stream_sid": stream_sid,
                        "error_type": type(e).__name__,
                    },
                )

        async def process_transcripts():
            """
            Process STT transcripts and generate AI responses.

            Flow:
            1. Get transcript from STT queue (interim or final)
            2. If interim + is_speaking → barge-in detected
            3. If final → add to conversation, call OpenAI
            4. Stream OpenAI response text to TTS
            5. Stream TTS audio to Twilio

            Performance tracking:
            - STT → LLM latency: ~500ms
            - LLM → TTS first byte: ~300ms
            - Barge-in response: ~200ms
            """
            nonlocal is_speaking

            try:
                while True:
                    # Get next transcript (blocks until available)
                    transcript_data = await stt.get_transcript()

                    if not transcript_data:
                        # Queue empty, small delay before retry
                        await asyncio.sleep(0.01)
                        continue

                    transcript_type = transcript_data.get("type")
                    transcript_text = transcript_data.get("text", "").strip()

                    if not transcript_text:
                        continue

                    # Handle interim results (barge-in detection)
                    # call-gpt pattern: Only trigger if audio is actively playing (marks.length > 0) AND text is substantial (> 5 chars)
                    if transcript_type == "interim":
                        if len(marks) > 0 and len(transcript_text) > 5:
                            logger.info(f"BARGE-IN DETECTED: User spoke while audio playing (marks={len(marks)}): '{transcript_text}'")

                            # Clear Twilio audio playback immediately
                            await websocket.send_text(
                                json.dumps({"event": "clear", "streamSid": stream_sid})
                            )

                            # Clear TTS audio queue
                            await tts.clear()

                            # Clear audio buffer to prevent buffered audio from being sent
                            audio_buffer.clear()

                            # Stop speaking flag
                            is_speaking = False

                            logger.info("Audio cleared for barge-in")

                    # Handle final transcripts (complete utterances)
                    elif transcript_type == "final" and transcript_data.get("speech_final"):
                        user_message = transcript_text
                        logger.info(f"[VOICE] ===== USER SAID: {user_message} =====")

                        # Update last user input time for silence detection
                        nonlocal last_user_input_time, silence_prompted
                        last_user_input_time = time.time()
                        silence_prompted = False  # Reset silence prompt flag

                        # Add to conversation history
                        openai.add_user_message(user_message)

                        # Generate AI response with streaming
                        is_speaking = True
                        response_text = ""
                        sentence_buffer = ""

                        # Start tracking LLM latency
                        metrics.start_llm()
                        logger.info("[VOICE] Calling OpenAI to generate response...")

                        # Create task to stream audio to Twilio in parallel
                        async def stream_audio_to_twilio():
                            """Stream audio from TTS to Twilio as it arrives."""
                            chunks_sent = 0
                            try:
                                while is_speaking:
                                    try:
                                        # Wait for audio with timeout
                                        audio_chunk = await asyncio.wait_for(
                                            tts.audio_queue.get(),
                                            timeout=0.5  # 500ms timeout
                                        )

                                        chunks_sent += 1

                                        # Track TTS first byte
                                        if chunks_sent == 1:
                                            metrics.track_tts_first_byte()

                                        # Send audio to Twilio (base64 encode mulaw)
                                        await websocket.send_text(
                                            json.dumps({
                                                "event": "media",
                                                "streamSid": stream_sid,
                                                "media": {
                                                    "payload": base64.b64encode(audio_chunk).decode("utf-8")
                                                },
                                            })
                                        )

                                        # Send mark only every 10 chunks to reduce overhead (prevents choppy audio)
                                        # Still provides accurate barge-in detection while keeping marks array small
                                        if chunks_sent % 10 == 1:  # Chunks 1, 11, 21, 31...
                                            mark_label = str(uuid.uuid4())
                                            await websocket.send_text(
                                                json.dumps({
                                                    "event": "mark",
                                                    "streamSid": stream_sid,
                                                    "mark": {"name": mark_label},
                                                })
                                            )
                                            marks.append(mark_label)
                                            logger.debug(f"[VOICE] Sent audio chunk {chunks_sent} with mark {mark_label}")
                                        else:
                                            logger.debug(f"[VOICE] Sent audio chunk {chunks_sent} (no mark)")

                                    except asyncio.TimeoutError:
                                        # No audio for 500ms, check if we're still speaking
                                        if not is_speaking:
                                            break
                                        continue

                            except Exception as e:
                                logger.error(f"[VOICE] Error streaming audio to Twilio: {e}")
                            finally:
                                logger.info(f"[VOICE] Finished streaming {chunks_sent} audio chunks to Twilio")

                        # Start audio streaming task
                        audio_task = asyncio.create_task(stream_audio_to_twilio())

                        # Stream LLM response and send to TTS incrementally
                        first_token_tracked = False
                        async for event in openai.generate_response(stream=True):
                            if event["type"] == "content_delta":
                                # Track first token latency
                                if not first_token_tracked:
                                    metrics.track_llm_first_token()
                                    first_token_tracked = True

                                # Accumulate chunks and send to TTS with optimized buffering
                                # Reference: Deepgram implementation sends chunks immediately for low latency
                                chunk = event["text"]
                                response_text += chunk
                                sentence_buffer += chunk
                                logger.debug(f"[VOICE] Got OpenAI chunk: '{chunk}'")

                                # Send on punctuation OR every 5 words to minimize latency
                                # Aggressive buffering for faster response (reference: call-gpt uses 5-10 word chunks)
                                stripped_buffer = sentence_buffer.strip()
                                word_count = len(stripped_buffer.split())

                                should_send = False
                                if stripped_buffer and stripped_buffer[-1] in ".!?:;":
                                    # Send complete sentences
                                    should_send = True
                                elif word_count >= 5:
                                    # Send partial phrases to avoid long delays (reduced from 10)
                                    should_send = True

                                if should_send:
                                    logger.info(f"[VOICE] Sending to TTS ({word_count} words): '{stripped_buffer[:100]}...'")
                                    await tts.send_text(stripped_buffer)
                                    sentence_buffer = ""

                            elif event["type"] == "tool_call":
                                # Tool is being executed - provide immediate feedback to avoid silence
                                # Reference: call-gpt "say before tool" pattern for better UX
                                tool_name = event["name"]
                                logger.info(f"[VOICE] Tool executing: {tool_name}")

                                # Send immediate feedback based on tool type
                                tool_feedback_map = {
                                    "lookup_customer": "Let me look that up for you...",
                                    "search_customers_by_name": "Let me search for that customer...",
                                    "get_appointment_details": "Let me check on that appointment...",
                                    "schedule_appointment": "Let me schedule that for you...",
                                    "get_available_timeslots": "Let me check available times...",
                                }

                                feedback_message = tool_feedback_map.get(tool_name, "Just a moment...")

                                # Send feedback immediately to TTS
                                logger.info(f"[VOICE] Sending tool feedback: '{feedback_message}'")
                                await tts.send_text(feedback_message)

                                # Track that we provided feedback (add to response_text for context)
                                response_text += feedback_message + " "

                            elif event["type"] == "tool_result":
                                # Tool execution completed
                                logger.info(f"[VOICE] Tool completed: {event.get('call_id')}")

                            elif event["type"] == "error":
                                # Error in response generation
                                logger.error(f"[VOICE] OpenAI ERROR: {event['message']}")
                                is_speaking = False
                                break

                            elif event["type"] == "done":
                                # Response generation complete
                                logger.info(f"[VOICE] ===== ASSISTANT RESPONSE: {response_text} =====")

                                # Send any remaining text to TTS
                                if sentence_buffer.strip():
                                    logger.info(f"[VOICE] Sending final text to TTS: '{sentence_buffer}'")
                                    await tts.send_text(sentence_buffer)

                                # Flush TTS to finalize audio generation
                                await tts.flush()
                                break

                        # Wait a bit for final audio chunks
                        await asyncio.sleep(0.5)

                        # Stop speaking flag
                        is_speaking = False

                        # Wait for audio streaming to complete
                        await audio_task

                        # Detect conversation end (goodbye detection)
                        # More lenient detection - trigger on goodbye phrases in last 50% of response
                        response_lower = response_text.lower()
                        goodbye_phrases = [
                            "goodbye", "bye bye", "bye", "thank you, goodbye", "thanks, goodbye",
                            "have a good day", "talk to you later", "see you later",
                            "have a great day", "take care", "goodbye!"
                        ]

                        # Trigger if goodbye is in the last 50% of the response (lowered from 70%)
                        # This ensures we catch shorter goodbyes while avoiding mid-conversation false positives
                        trigger_hangup = False
                        for phrase in goodbye_phrases:
                            phrase_pos = response_lower.rfind(phrase)
                            if phrase_pos >= 0:
                                # Check if phrase is in last 50% of response
                                relative_pos = phrase_pos / len(response_lower) if len(response_lower) > 0 else 0
                                if relative_pos >= 0.5:
                                    trigger_hangup = True
                                    logger.info(f"[VOICE] Goodbye phrase '{phrase}' detected at position {relative_pos:.1%}")
                                    break

                        if trigger_hangup:
                            logger.info(f"[VOICE] Goodbye detected - waiting for audio to finish playing ({len(marks)} marks remaining)")

                            # Wait for all audio marks to clear (audio finished playing)
                            max_wait = 30  # Maximum 30 seconds to wait
                            wait_start = time.time()
                            while len(marks) > 0 and (time.time() - wait_start) < max_wait:
                                await asyncio.sleep(0.1)
                                if len(marks) > 0:
                                    logger.debug(f"[VOICE] Waiting for {len(marks)} marks to clear...")

                            if len(marks) > 0:
                                logger.warning(f"[VOICE] Timeout waiting for marks to clear ({len(marks)} remaining)")
                            else:
                                logger.info(f"[VOICE] All audio finished playing, terminating call")

                            # Send hangup event to Twilio (clears audio queue)
                            try:
                                await websocket.send_text(
                                    json.dumps({
                                        "event": "hangup",
                                        "streamSid": stream_sid
                                    })
                                )
                                logger.info(f"[VOICE] Hangup event sent to Twilio")
                            except Exception as e:
                                logger.error(f"[VOICE] Failed to send hangup event: {e}")

                            # Actually terminate the call via Twilio API
                            if call_sid:
                                try:
                                    twilio_client = TwilioClient(
                                        settings.TWILIO_ACCOUNT_SID,
                                        settings.TWILIO_AUTH_TOKEN
                                    )
                                    twilio_client.calls(call_sid).update(status='completed')
                                    logger.info(f"[VOICE] Call {call_sid} terminated via Twilio API")
                                except Exception as e:
                                    logger.error(f"[VOICE] Failed to terminate call via Twilio API: {e}")

                            # Exit the transcript processing loop
                            break

                        # Log performance metrics
                        perf_data = metrics.get_metrics()
                        logger.info(
                            f"[PERFORMANCE] LLM TTFT: {perf_data.get('llm_time_to_first_token_ms', 'N/A')}ms | "
                            f"TTS TTFB: {perf_data.get('tts_time_to_first_byte_ms', 'N/A')}ms"
                        )

                        # Reset metrics for next turn
                        metrics.reset()

                        # Update session in Redis with conversation history
                        if call_sid:
                            try:
                                await update_session(
                                    call_sid,
                                    {
                                        "conversation_history": openai.get_conversation_history(),
                                        "last_updated": datetime.now(timezone.utc).isoformat(),
                                    },
                                )
                            except Exception as e:
                                logger.warning(f"Failed to update session in Redis: {e}")

            except Exception as e:
                logger.error(
                    f"Error in process_transcripts: {e}",
                    exc_info=True,
                    extra={
                        "call_sid": call_sid,
                        "stream_sid": stream_sid,
                        "error_type": type(e).__name__,
                    },
                )

        async def monitor_silence():
            """
            Monitor for prolonged silence and prompt user.

            After 15 seconds of silence: prompt "Hello, are you still there?"
            After 20 seconds total (5 more after prompt): hang up
            """
            nonlocal is_speaking, last_user_input_time, silence_prompted

            try:
                while True:
                    await asyncio.sleep(1)  # Check every second

                    # Skip if AI is currently speaking
                    if is_speaking or len(marks) > 0:
                        continue

                    silence_duration = time.time() - last_user_input_time

                    # First prompt after 15 seconds
                    if silence_duration >= 15 and not silence_prompted:
                        logger.info(f"[SILENCE DETECTION] 15s of silence detected, prompting user")
                        silence_prompted = True

                        # Generate prompt through TTS
                        prompt_message = "Hello, are you still there?"
                        openai.add_assistant_message(prompt_message)

                        # Send through TTS
                        is_speaking = True
                        async for audio_chunk in tts.text_to_speech(prompt_message):
                            if audio_chunk:
                                audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")

                                # Send audio with mark tracking
                                await websocket.send_text(
                                    json.dumps({
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {"payload": audio_b64},
                                    })
                                )

                                mark_label = str(uuid.uuid4())
                                await websocket.send_text(
                                    json.dumps({
                                        "event": "mark",
                                        "streamSid": stream_sid,
                                        "mark": {"name": mark_label},
                                    })
                                )
                                marks.append(mark_label)

                        is_speaking = False
                        logger.info("[SILENCE DETECTION] Prompt sent, waiting 5 more seconds")

                    # Hang up after 20 seconds total (5 seconds after prompt)
                    elif silence_duration >= 20 and silence_prompted:
                        logger.info(f"[SILENCE DETECTION] 20s total silence, hanging up")

                        # Wait for any remaining audio to finish
                        max_wait = 10
                        wait_start = time.time()
                        while len(marks) > 0 and (time.time() - wait_start) < max_wait:
                            await asyncio.sleep(0.1)

                        # Terminate call
                        try:
                            await websocket.send_text(
                                json.dumps({"event": "hangup", "streamSid": stream_sid})
                            )
                            logger.info("[SILENCE DETECTION] Hangup event sent")
                        except Exception as e:
                            logger.error(f"[SILENCE DETECTION] Failed to send hangup: {e}")

                        if call_sid:
                            try:
                                twilio_client = TwilioClient(
                                    settings.TWILIO_ACCOUNT_SID,
                                    settings.TWILIO_AUTH_TOKEN
                                )
                                twilio_client.calls(call_sid).update(status='completed')
                                logger.info(f"[SILENCE DETECTION] Call {call_sid} terminated")
                            except Exception as e:
                                logger.error(f"[SILENCE DETECTION] Failed to terminate call: {e}")

                        break  # Exit monitoring loop

            except asyncio.CancelledError:
                logger.debug("Silence monitoring cancelled")
            except Exception as e:
                logger.error(f"Error in silence monitoring: {e}", exc_info=True)

        # Run three tasks concurrently using asyncio.gather
        logger.info("Starting concurrent tasks (receive + process + silence monitoring)")
        await asyncio.gather(
            receive_from_twilio(),
            process_transcripts(),
            monitor_silence()
        )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")

    except Exception as e:
        logger.error(
            f"Error in media stream handler: {e}",
            exc_info=True,
            extra={
                "call_sid": call_sid,
                "stream_sid": stream_sid,
                "caller_phone": caller_phone,
                "error_type": type(e).__name__,
            },
        )

        # Attempt to send graceful error message to caller
        try:
            if websocket and stream_sid:
                # Clear any pending audio
                await websocket.send_text(
                    json.dumps({"event": "clear", "streamSid": stream_sid})
                )

                # Note: We cannot easily send TTS audio here since services may be broken
                # In production, consider having a pre-recorded error message
                logger.info("Sent clear event to Twilio due to error")
        except Exception as fallback_error:
            logger.error(f"Failed to send error notification to caller: {fallback_error}")

    finally:
        # Cleanup: Close all services and save final state
        logger.info("Cleaning up resources...")

        # Close STT
        if stt:
            try:
                await stt.close()
                logger.debug("STT closed")
            except Exception as e:
                logger.error(f"Error closing STT: {e}")

        # Close TTS
        if tts:
            try:
                await tts.disconnect()
                logger.debug("TTS disconnected")
            except Exception as e:
                logger.error(f"Error closing TTS: {e}")

        # Close database session
        if db:
            try:
                await db.close()
                logger.debug("Database session closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")

        # Save final session state to Redis
        if call_sid and openai:
            try:
                await update_session(
                    call_sid,
                    {
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                        "conversation_history": openai.get_conversation_history(),
                        "total_tokens": openai.get_token_usage(),
                        "status": "completed",
                    },
                )
                logger.info(f"Final session state saved for call: {call_sid}")
            except Exception as e:
                logger.warning(f"Failed to save final session state: {e}")

        logger.info("Cleanup complete, WebSocket closed")


@router.websocket("/ws")
async def voice_websocket_legacy(websocket: WebSocket):
    """
    Legacy WebSocket endpoint (kept for backward compatibility).

    Redirects to /media-stream endpoint.
    """
    logger.warning("Legacy /ws endpoint accessed, use /media-stream instead")
    await handle_media_stream(websocket)
