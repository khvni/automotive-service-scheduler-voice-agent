"""
Deepgram Text-to-Speech service for real-time audio synthesis.

This service handles WebSocket-based TTS for Twilio audio streams
using Deepgram's Aura model optimized for natural-sounding speech.
"""

import asyncio
import logging
import time
from typing import Optional

from deepgram import DeepgramClient, DeepgramClientOptions
try:
    from deepgram.core.events import EventType
    from deepgram.extensions.types.sockets import (
        SpeakV1ControlMessage,
        SpeakV1SocketClientResponse,
        SpeakV1TextMessage,
    )
except ImportError:
    # Deepgram SDK 3.8.0 has different imports
    EventType = None
    SpeakV1ControlMessage = dict
    SpeakV1SocketClientResponse = dict
    SpeakV1TextMessage = dict

from .tts_interface import TTSInterface

logger = logging.getLogger(__name__)


class DeepgramTTSService(TTSInterface):
    """
    Deepgram Text-to-Speech service for real-time synthesis.

    Configured for Twilio phone audio streams with:
    - mulaw encoding at 8kHz (phone quality)
    - aura-2-asteria-en model (natural voice)
    - Streaming support for low-latency response
    - Barge-in support (clear command)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "aura-2-asteria-en",
        encoding: str = "mulaw",
        sample_rate: int = 8000,
    ):
        """
        Initialize Deepgram TTS service.

        Args:
            api_key: Deepgram API key
            model: TTS model to use (default: aura-2-asteria-en)
            encoding: Audio encoding (default: mulaw for Twilio)
            sample_rate: Audio sample rate in Hz (default: 8000 for phone)
        """
        self.api_key = api_key
        self.model = model
        self.encoding = encoding
        self.sample_rate = sample_rate

        self.client: Optional[DeepgramClient] = None
        self.connection = None
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self._is_connected = False

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
        return self._is_connected

    async def connect(self) -> None:
        """
        Establish WebSocket connection to Deepgram TTS.

        Sets up event listeners for:
        - Open: Connection established
        - Message: Audio data or control messages
        - Close: Connection closed
        - Error: Error handling

        Raises:
            Exception: If connection fails
        """
        try:
            # Create Deepgram client (handles both sync and async)
            config = DeepgramClientOptions(options={"keepalive": "true"})
            self.client = DeepgramClient(self.api_key, config)

            # Create speak connection with Twilio-compatible settings (SDK v3.8.0)
            # Use asyncwebsocket.v("1") for async TTS operations
            self.connection = self.client.speak.asyncwebsocket.v("1")

            # Set up event listeners
            self.connection.on(EventType.OPEN, self._on_open)
            self.connection.on(EventType.MESSAGE, self._on_message)
            self.connection.on(EventType.CLOSE, self._on_close)
            self.connection.on(EventType.ERROR, self._on_error)

            # Start the connection with options (SDK v3.8.0)
            options = {
                "model": self.model,
                "encoding": self.encoding,
                "sample_rate": self.sample_rate,
            }

            if not await self.connection.start(options):
                raise Exception("Failed to start Deepgram TTS connection")

            self._is_connected = True

            logger.info(
                f"Connected to Deepgram TTS: model={self.model}, "
                f"encoding={self.encoding}, sample_rate={self.sample_rate}"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram TTS: {e}")
            raise

    async def send_text(self, text: str) -> None:
        """
        Send text chunk to be converted to speech.

        Supports streaming multiple text chunks for low-latency synthesis.
        Audio starts playing as soon as first chunk is synthesized.

        Args:
            text: Text to synthesize

        Raises:
            Exception: If not connected or send fails
        """
        if not self._is_connected or not self.connection:
            raise Exception("Not connected to Deepgram TTS")

        try:
            # Track start time for performance metrics
            if self.tts_start_time is None:
                self.tts_start_time = time.time()
                self.first_byte_received = False

            # Send text message (SDK v3.8.0 uses plain string)
            await self.connection.send_text(text)

            logger.debug(f"Sent text to TTS: {text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to send text to Deepgram TTS: {e}")
            raise

    async def flush(self) -> None:
        """
        Signal end of text stream and flush remaining audio.

        Tells Deepgram that no more text is coming, allowing it
        to finalize synthesis and return any buffered audio.
        """
        if not self._is_connected or not self.connection:
            logger.warning("Cannot flush: not connected to Deepgram TTS")
            return

        try:
            # SDK v3.8.0 uses plain flush method
            await self.connection.flush()
            logger.debug("Sent Flush command to Deepgram TTS")

        except Exception as e:
            logger.error(f"Failed to flush Deepgram TTS: {e}")

    async def clear(self) -> None:
        """
        Clear audio queue and stop current synthesis (barge-in).

        Used when user interrupts AI speech. Clears both the local
        audio queue and tells Deepgram to stop generating audio.
        """
        try:
            # Clear local audio queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            # Send clear command to Deepgram if connected (SDK v3.8.0)
            if self._is_connected and self.connection:
                await self.connection.clear()
                logger.debug("Sent Clear command to Deepgram TTS (barge-in)")

            # Reset timing metrics
            self.tts_start_time = None
            self.first_byte_received = False

        except Exception as e:
            logger.error(f"Failed to clear Deepgram TTS: {e}")

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
        logger.info("Closing Deepgram TTS connection")

        self._is_connected = False

        # Close connection (SDK v3.8.0 uses finish method)
        if self.connection:
            try:
                self.connection.finish()
            except Exception as e:
                logger.error(f"Error closing Deepgram TTS connection: {e}")

        # Clear audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Reset timing metrics
        self.tts_start_time = None
        self.first_byte_received = False

        logger.info("Deepgram TTS connection closed")

    # Event handlers

    async def _on_open(self, *args, **kwargs) -> None:
        """Handle connection open event."""
        logger.info("Deepgram TTS: Connected")

    async def _on_message(self, *args, **kwargs) -> None:
        """
        Handle message event.

        Processes both audio data (bytes) and control messages (JSON).
        Audio data is queued for streaming to Twilio.
        """
        # Extract message from args
        message = kwargs.get("message") or (args[1] if len(args) > 1 else args[0])

        # Check if it's audio data (bytes) or control message
        if isinstance(message, bytes):
            # Track time to first byte for performance metrics
            if not self.first_byte_received and self.tts_start_time:
                ttfb = (time.time() - self.tts_start_time) * 1000  # ms
                logger.info(f"Deepgram TTS: Time to First Byte = {ttfb:.2f}ms")
                self.first_byte_received = True

            # Add audio to queue for streaming
            await self.audio_queue.put(message)
            logger.debug(f"Deepgram TTS: Received audio chunk ({len(message)} bytes)")

        else:
            # Control message (JSON response)
            try:
                msg_type = getattr(message, "type", "Unknown")
                logger.debug(f"Deepgram TTS: Received {msg_type} event")

                # Handle specific message types if needed
                if msg_type == "Flushed":
                    logger.debug("Deepgram TTS: Flush complete")
                elif msg_type == "Cleared":
                    logger.debug("Deepgram TTS: Clear complete (barge-in)")
                elif msg_type == "Metadata":
                    logger.debug(f"Deepgram TTS: Metadata = {message}")

            except Exception as e:
                logger.debug(f"Deepgram TTS: Received non-standard message: {message}")

    async def _on_close(self, *args, **kwargs) -> None:
        """Handle connection close event."""
        logger.info("Deepgram TTS: Disconnected")
        self._is_connected = False

    async def _on_error(self, *args, **kwargs) -> None:
        """Handle error event."""
        error = kwargs.get("error") or (args[1] if len(args) > 1 else args[0])
        logger.error(f"Deepgram TTS: Error received: {error}")
