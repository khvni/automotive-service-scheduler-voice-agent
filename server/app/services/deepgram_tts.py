"""
Deepgram Text-to-Speech service for real-time audio synthesis.

This service uses Deepgram's WebSocket API for Twilio audio streams
using Deepgram's Aura model optimized for natural-sounding speech.
"""

import asyncio
import json
import logging
import time
from typing import Optional

import websockets
from websockets.exceptions import WebSocketException

from .tts_interface import TTSInterface

logger = logging.getLogger(__name__)


class DeepgramTTSService(TTSInterface):
    """
    Deepgram Text-to-Speech service for real-time synthesis using WebSocket.

    Configured for Twilio phone audio streams with:
    - mulaw encoding at 8kHz (phone quality)
    - aura-asteria-en model (natural voice)
    - WebSocket streaming for low-latency audio delivery
    """

    def __init__(
        self,
        api_key: str,
        model: str = "aura-asteria-en",
        encoding: str = "mulaw",
        sample_rate: int = 8000,
    ):
        """
        Initialize Deepgram TTS service.

        Args:
            api_key: Deepgram API key
            model: TTS model to use (default: aura-asteria-en)
            encoding: Audio encoding (default: mulaw for Twilio)
            sample_rate: Audio sample rate in Hz (default: 8000 for phone)
        """
        self.api_key = api_key
        self.model = model
        self.encoding = encoding
        self.sample_rate = sample_rate

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self._is_connected = False
        self._receive_task: Optional[asyncio.Task] = None

        # Performance tracking
        self.tts_start_time: Optional[float] = None
        self.first_byte_received = False

        logger.info(
            f"DeepgramTTSService initialized: model={model}, "
            f"encoding={encoding}, sample_rate={sample_rate}"
        )

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to Deepgram TTS."""
        return self._is_connected and self.ws is not None

    async def connect(self) -> None:
        """
        Connect to Deepgram TTS WebSocket API.

        Raises:
            Exception: If connection fails
        """
        try:
            # Build WebSocket URL with query parameters
            ws_url = (
                f"wss://api.deepgram.com/v1/speak"
                f"?model={self.model}"
                f"&encoding={self.encoding}"
                f"&sample_rate={self.sample_rate}"
                f"&container=none"
            )

            # Connect to Deepgram TTS WebSocket
            self.ws = await websockets.connect(
                ws_url,
                extra_headers={"Authorization": f"Token {self.api_key}"},
            )

            self._is_connected = True

            # Start background task to receive audio
            self._receive_task = asyncio.create_task(self._receive_audio())

            logger.info(
                f"[TTS] Connected to Deepgram TTS WebSocket: model={self.model}, "
                f"encoding={self.encoding}, sample_rate={self.sample_rate}"
            )

        except Exception as e:
            logger.error(f"[TTS] Failed to connect to Deepgram TTS: {e}")
            raise

    async def _receive_audio(self) -> None:
        """
        Background task to receive audio chunks from Deepgram WebSocket.

        Streams audio chunks directly to the queue as they arrive.
        """
        try:
            first_byte = False
            total_bytes = 0
            chunk_count = 0

            logger.info(f"[TTS] Started receiving audio from WebSocket")

            async for message in self.ws:
                if isinstance(message, bytes):
                    # Track time to first byte
                    if not first_byte:
                        if self.tts_start_time:
                            ttfb = (time.time() - self.tts_start_time) * 1000  # ms
                            logger.info(f"[TTS] Time to First Byte = {ttfb:.2f}ms")
                        first_byte = True
                        self.first_byte_received = True

                    # Add audio to queue for streaming
                    await self.audio_queue.put(message)
                    total_bytes += len(message)
                    chunk_count += 1
                    logger.debug(
                        f"[TTS] Queued chunk {chunk_count}: {len(message)} bytes "
                        f"(total: {total_bytes} bytes)"
                    )

        except WebSocketException as e:
            logger.error(f"[TTS] WebSocket error in receive: {e}")
        except Exception as e:
            logger.error(f"[TTS] ERROR receiving audio: {e}", exc_info=True)
        finally:
            logger.info(f"[TTS] Stopped receiving audio")

    async def send_text(self, text: str) -> None:
        """
        Send text to be converted to speech using WebSocket streaming.

        Audio chunks will be available in the queue as they arrive.

        Args:
            text: Text to synthesize

        Raises:
            Exception: If not connected or send fails
        """
        if not self.is_connected or not self.ws:
            raise Exception("Not connected to Deepgram TTS")

        try:
            # Track start time for TTFB measurement
            self.tts_start_time = time.time()
            self.first_byte_received = False

            logger.info(f"[TTS] Sending text: '{text[:100]}...'")

            # Send text to TTS WebSocket
            message = json.dumps({"type": "Speak", "text": text})
            await self.ws.send(message)

            logger.debug(f"[TTS] Text sent to WebSocket")

        except Exception as e:
            logger.error(f"[TTS] ERROR sending text: {e}", exc_info=True)
            raise

    async def flush(self) -> None:
        """
        Flush any pending TTS synthesis.

        Sends a Flush message to ensure all queued text is synthesized.
        """
        if not self.is_connected or not self.ws:
            logger.warning("[TTS] Cannot flush - not connected")
            return

        try:
            logger.info("[TTS] Flushing TTS queue")
            message = json.dumps({"type": "Flush"})
            await self.ws.send(message)
        except Exception as e:
            logger.error(f"[TTS] ERROR flushing: {e}")

    async def clear(self) -> None:
        """
        Clear audio queue and stop current synthesis (barge-in).

        Sends a Clear message to Deepgram and clears the local audio queue.
        """
        try:
            # Send Clear to Deepgram to stop synthesis
            if self.is_connected and self.ws:
                message = json.dumps({"type": "Clear"})
                await self.ws.send(message)
                logger.info("[TTS] Sent Clear to Deepgram")

            # Clear local audio queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            logger.info("[TTS] Cleared TTS audio queue (barge-in)")

            # Reset timing metrics
            self.tts_start_time = None
            self.first_byte_received = False

        except Exception as e:
            logger.error(f"[TTS] Failed to clear: {e}")

    async def get_audio(self) -> Optional[bytes]:
        """
        Get next audio chunk from the queue.

        Non-blocking. Returns None if queue is empty.
        Audio is in mulaw format at 8kHz, ready for Twilio.

        Returns:
            Audio bytes or None if no audio available
        """
        try:
            return self.audio_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def disconnect(self) -> None:
        """
        Close connection to Deepgram TTS and cleanup resources.
        """
        logger.info("[TTS] Closing Deepgram TTS connection")

        self._is_connected = False

        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.error(f"[TTS] Error closing WebSocket: {e}")

        # Clear audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Reset timing metrics
        self.tts_start_time = None
        self.first_byte_received = False

        logger.info("[TTS] Deepgram TTS connection closed")
