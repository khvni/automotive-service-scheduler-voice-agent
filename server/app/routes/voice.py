"""
Voice call handling routes and WebSocket endpoints.

This module implements the main WebSocket handler for Twilio Media Streams,
orchestrating STT, LLM, TTS, and tool execution for real-time voice conversations.
"""

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config import settings
from app.services.database import get_db
from app.services.deepgram_stt import DeepgramSTTService
from app.services.deepgram_tts import DeepgramTTSService
from app.services.openai_service import OpenAIService
from app.services.redis_client import get_session, set_session, update_session
from app.services.tool_definitions import TOOL_SCHEMAS
from app.services.tool_router import ToolRouter
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()


# System prompt for the AI assistant
SYSTEM_PROMPT = """You are Sophie, a friendly and professional receptionist at Otto's Auto,
a full-service automotive repair shop.

Your role:
- Help customers schedule service appointments
- Answer questions about services, hours, and pricing
- Look up customer information and service history
- Provide a warm, efficient customer service experience

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

Remember: You're helpful, knowledgeable, and focused on getting customers scheduled efficiently."""


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
async def handle_incoming_call():
    """
    Twilio webhook for incoming calls.
    Returns TwiML to establish WebSocket connection.
    """
    # TODO: Update with actual domain (from environment variable)
    ws_url = f"wss://{settings.BASE_URL}/api/v1/voice/media-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Google.en-US-Chirp3-HD-Aoede">
        Please wait while we connect you to our AI assistant.
    </Say>
    <Pause length="1"/>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/incoming-reminder")
async def handle_incoming_reminder():
    """
    Twilio webhook for outbound reminder calls.
    Returns TwiML to establish WebSocket connection with reminder context.

    This endpoint is called by the worker job when making outbound reminder calls.
    The WebSocket handler will detect the reminder context and use appropriate prompts.
    """
    ws_url = f"wss://{settings.BASE_URL.replace('https://', '').replace('http://', '')}/api/v1/voice/media-stream"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="call_type" value="outbound_reminder"/>
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

    # Services (initialized in try block)
    stt: Optional[DeepgramSTTService] = None
    tts: Optional[DeepgramTTSService] = None
    openai: Optional[OpenAIService] = None
    db: Optional[AsyncSession] = None

    try:
        # Initialize services
        logger.info("Initializing services (STT, TTS, OpenAI)")

        stt = DeepgramSTTService(settings.DEEPGRAM_API_KEY)
        tts = DeepgramTTSService(settings.DEEPGRAM_API_KEY)
        openai = OpenAIService(
            api_key=settings.OPENAI_API_KEY, model="gpt-4o", temperature=0.8, max_tokens=1000
        )

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

                    elif event == "media":
                        # Decode audio and send to STT
                        audio_payload = data["media"]["payload"]
                        audio_bytes = base64.b64decode(audio_payload)
                        await stt.send_audio(audio_bytes)

                    elif event == "mark":
                        # Mark acknowledgment (used for synchronization in reference)
                        mark_name = data["mark"].get("name")
                        logger.debug(f"Mark received: {mark_name}")

                    elif event == "stop":
                        logger.info("Twilio Media Stream stop event received")
                        break

            except WebSocketDisconnect:
                logger.info("Twilio disconnected (receive task)")
            except Exception as e:
                logger.error(f"Error in receive_from_twilio: {e}", exc_info=True)

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
                    if transcript_type == "interim":
                        if is_speaking:
                            logger.info(f"BARGE-IN DETECTED: User spoke while AI was speaking")

                            # Clear Twilio audio playback immediately
                            await websocket.send_json({"event": "clear", "streamSid": stream_sid})

                            # Clear TTS audio queue
                            await tts.clear()

                            # Stop speaking flag
                            is_speaking = False

                            logger.info("Audio cleared for barge-in")

                    # Handle final transcripts (complete utterances)
                    elif transcript_type == "final" and transcript_data.get("speech_final"):
                        user_message = transcript_text
                        logger.info(f"[VOICE] ===== USER SAID: {user_message} =====")

                        # Add to conversation history
                        openai.add_user_message(user_message)

                        # Generate AI response with streaming
                        is_speaking = True
                        response_text = ""

                        logger.info("[VOICE] Calling OpenAI to generate response...")

                        async for event in openai.generate_response(stream=True):
                            if event["type"] == "content_delta":
                                # Accumulate text chunks
                                chunk = event["text"]
                                response_text += chunk
                                logger.info(f"[VOICE] Got OpenAI chunk: '{chunk}'")

                            elif event["type"] == "tool_call":
                                # Tool is being executed (logged by OpenAI service)
                                tool_name = event["name"]
                                logger.info(f"[VOICE] Tool executing: {tool_name}")

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

                                # Send complete response to TTS once
                                if response_text.strip():
                                    logger.info(f"[VOICE] Sending complete response to TTS ({len(response_text)} chars)")
                                    await tts.send_text(response_text)
                                    logger.info(f"[VOICE] TTS send_text() returned")

                                # Flush TTS to finalize audio generation
                                await tts.flush()
                                break

                        # Stream TTS audio to Twilio
                        logger.info("[VOICE] Starting to stream audio chunks to Twilio")
                        consecutive_empty = 0
                        MAX_EMPTY_READS = 50  # 500ms timeout (50 * 10ms)
                        chunks_sent = 0

                        while is_speaking:
                            audio_chunk = await tts.get_audio()

                            if audio_chunk is None:
                                # No audio available
                                consecutive_empty += 1

                                if consecutive_empty >= MAX_EMPTY_READS:
                                    # No audio for 500ms, assume done
                                    is_speaking = False
                                    logger.info(f"[VOICE] Audio stream complete - sent {chunks_sent} chunks to Twilio")
                                    break

                                # Small delay before next check
                                await asyncio.sleep(0.01)
                                continue

                            # Got audio chunk, reset timeout counter
                            consecutive_empty = 0
                            chunks_sent += 1

                            # Send audio to Twilio (base64 encode mulaw)
                            await websocket.send_json(
                                {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {
                                        "payload": base64.b64encode(audio_chunk).decode("utf-8")
                                    },
                                }
                            )
                            logger.info(f"[VOICE] Sent audio chunk {chunks_sent} to Twilio ({len(audio_chunk)} bytes)")

                        logger.info(f"[VOICE] Finished streaming {chunks_sent} audio chunks to Twilio")

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
                logger.error(f"Error in process_transcripts: {e}", exc_info=True)

        # Run both tasks concurrently using asyncio.gather
        logger.info("Starting concurrent tasks (receive + process)")
        await asyncio.gather(receive_from_twilio(), process_transcripts())

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")

    except Exception as e:
        logger.error(f"Error in media stream handler: {e}", exc_info=True)

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
