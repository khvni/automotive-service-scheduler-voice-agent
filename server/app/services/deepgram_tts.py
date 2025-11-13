"""
Deepgram Text-to-Speech service for real-time audio synthesis.

This service uses Deepgram's REST streaming API for Twilio audio streams
using Deepgram's Aura model optimized for natural-sounding speech.
"""

import asyncio
import logging
import time
from typing import Optional

from deepgram import DeepgramClient, DeepgramClientOptions, SpeakOptions

from .tts_interface import TTSInterface

logger = logging.getLogger(__name__)


class DeepgramTTSService(TTSInterface):
    """
    Deepgram Text-to-Speech service for real-time synthesis.

    Configured for Twilio phone audio streams with:
    - mulaw encoding at 8kHz (phone quality)
    - aura-2-asteria-en model (natural voice)
    - REST streaming API for reliable audio delivery
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
        self.tts_client = None
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        self._is_connected = False
        self._current_stream = None

        # TTS options for REST API
        self.speak_options = SpeakOptions(
            model=model,
            encoding=encoding,
            sample_rate=sample_rate,
        )

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
        Initialize Deepgram TTS REST API client.

        Raises:
            Exception: If initialization fails
        """
        try:
            # Create Deepgram client
            config = DeepgramClientOptions(options={"keepalive": "true"})
            self.client = DeepgramClient(self.api_key, config)

            # Get REST API client for streaming TTS (SDK v3.8.0)
            self.tts_client = self.client.speak.asyncrest.v("1")

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
        Send text to be converted to speech using REST streaming API.

        Streams audio chunks directly to the audio queue as they arrive.

        Args:
            text: Text to synthesize

        Raises:
            Exception: If not connected or send fails
        """
        if not self._is_connected or not self.tts_client:
            raise Exception("Not connected to Deepgram TTS")

        try:
            # Track start time for performance metrics
            if self.tts_start_time is None:
                self.tts_start_time = time.time()
                self.first_byte_received = False

            logger.debug(f"Sending text to TTS: {text[:50]}...")

            # Stream audio using REST API (SDK v3.8.0)
            response = await self.tts_client.stream_raw(
                {"text": text},
                self.speak_options
            )

            # Process the streaming response
            async for chunk in response.aiter_bytes():
                if chunk:
                    # Track time to first byte
                    if not self.first_byte_received and self.tts_start_time:
                        ttfb = (time.time() - self.tts_start_time) * 1000  # ms
                        logger.info(f"Deepgram TTS: Time to First Byte = {ttfb:.2f}ms")
                        self.first_byte_received = True

                    # Add audio to queue for streaming
                    await self.audio_queue.put(chunk)
                    logger.debug(f"Deepgram TTS: Queued audio chunk ({len(chunk)} bytes)")

            # Reset timing for next synthesis
            self.tts_start_time = None
            self.first_byte_received = False

            logger.debug("TTS synthesis complete")

        except Exception as e:
            logger.error(f"Failed to synthesize with Deepgram TTS: {e}")
            raise

    async def flush(self) -> None:
        """
        Flush is not needed for REST API - each send_text completes fully.
        """
        pass

    async def clear(self) -> None:
        """
        Clear audio queue and stop current synthesis (barge-in).

        Clears the local audio queue to stop playback.
        """
        try:
            # Clear local audio queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

            logger.debug("Cleared TTS audio queue (barge-in)")

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
