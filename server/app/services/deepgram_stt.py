"""
Deepgram Speech-to-Text service for real-time audio transcription.

This service handles WebSocket-based live transcription of Twilio audio streams
using Deepgram's nova-2-phonecall model optimized for phone audio quality.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from deepgram import DeepgramClient, DeepgramClientOptions, LiveOptions, LiveTranscriptionEvents

logger = logging.getLogger(__name__)


class DeepgramSTTService:
    """
    Deepgram Speech-to-Text service for real-time transcription.

    Configured for Twilio phone audio streams with:
    - mulaw encoding at 8kHz (phone quality)
    - nova-2-phonecall model (optimized for telephony)
    - Interim results enabled for barge-in detection
    - Smart formatting for better readability
    """

    def __init__(self, api_key: str):
        """
        Initialize Deepgram STT service.

        Args:
            api_key: Deepgram API key
        """
        self.api_key = api_key
        self.client: Optional[DeepgramClient] = None
        self.connection = None
        self.transcript_queue: asyncio.Queue = asyncio.Queue()
        self.is_finals: List[str] = []
        self.is_connected = False
        self.keepalive_task: Optional[asyncio.Task] = None

        # Configuration for phone audio transcription
        self.live_options = LiveOptions(
            # Model configuration
            model="nova-2-phonecall",  # Optimized for phone audio
            language="en",
            # Formatting
            smart_format=True,  # Auto-capitalize, punctuate, format numbers
            # Audio configuration (Twilio uses mulaw encoding)
            encoding="mulaw",
            sample_rate=8000,  # Phone quality
            channels=1,
            # Real-time features
            interim_results=True,  # CRITICAL: enables barge-in detection
            no_delay=True,  # Minimize latency
            # End-of-speech detection
            endpointing=300,  # ms of silence to detect end of utterance
            utterance_end_ms=1000,  # ms to finalize utterance
        )

        logger.info("DeepgramSTTService initialized with nova-2-phonecall model")

    async def connect(self, max_retries: int = 3, backoff_factor: float = 1.5) -> None:
        """
        Establish WebSocket connection to Deepgram with retry logic.

        Sets up event listeners for:
        - Open: Connection established
        - Transcript: Real-time transcription results
        - UtteranceEnd: End of user utterance detection
        - Close: Connection closed
        - Error: Error handling
        - Warning: Warning messages

        Args:
            max_retries: Maximum number of connection attempts (default: 3)
            backoff_factor: Exponential backoff multiplier (default: 1.5)

        Raises:
            Exception: If connection fails after all retries
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                await self._attempt_connection()
                logger.info(f"Connected to Deepgram STT on attempt {attempt + 1}/{max_retries}")
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    f"STT connection attempt {attempt + 1}/{max_retries} failed: {e}"
                )

                if attempt < max_retries - 1:
                    delay = backoff_factor ** attempt
                    logger.info(f"Retrying STT connection in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"STT connection failed after {max_retries} attempts")

        # All retries exhausted
        raise Exception(f"Failed to connect to Deepgram STT after {max_retries} attempts: {last_error}")

    async def _attempt_connection(self) -> None:
        """
        Single connection attempt to Deepgram.

        Raises:
            Exception: If connection fails
        """
        try:
            # Create Deepgram client
            config = DeepgramClientOptions(options={"keepalive": "true"})
            self.client = DeepgramClient(self.api_key, config)

            # Create live transcription connection
            self.connection = self.client.listen.websocket.v("1")

            # Set up event listeners
            self.connection.on(LiveTranscriptionEvents.Open, self._on_open)
            self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
            self.connection.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)
            self.connection.on(LiveTranscriptionEvents.Close, self._on_close)
            self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
            self.connection.on(LiveTranscriptionEvents.Warning, self._on_warning)
            self.connection.on(LiveTranscriptionEvents.Metadata, self._on_metadata)

            # Start the connection (synchronous call)
            if not self.connection.start(self.live_options):
                raise Exception("Failed to start Deepgram connection")

            self.is_connected = True

            # Start keepalive task
            self.keepalive_task = asyncio.create_task(self._keepalive_loop())

            logger.debug("Deepgram STT connection attempt successful")

        except Exception as e:
            # Clean up connection/client on failure to prevent resource leaks
            logger.error(f"Failed to start Deepgram connection: {e}")
            if self.connection:
                try:
                    self.connection.finish()
                except:
                    pass
                self.connection = None
            self.client = None
            self.is_connected = False
            raise

    async def _keepalive_loop(self) -> None:
        """Send keepalive messages every 10 seconds to maintain connection."""
        try:
            while self.is_connected:
                await asyncio.sleep(10)
                if self.connection and self.is_connected:
                    # keep_alive() is synchronous
                    self.connection.keep_alive()
                    logger.debug("Sent keepalive to Deepgram")
        except asyncio.CancelledError:
            logger.debug("Keepalive loop cancelled")
        except Exception as e:
            logger.error(f"Error in keepalive loop: {e}")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """
        Send audio chunk to Deepgram for transcription.

        Args:
            audio_chunk: Raw audio bytes (mulaw encoded)

        Raises:
            Exception: If not connected or send fails
        """
        if not self.is_connected or not self.connection:
            raise Exception("Not connected to Deepgram")

        try:
            self.connection.send(audio_chunk)
        except Exception as e:
            logger.error(f"Failed to send audio to Deepgram: {e}")
            raise

    async def get_transcript(self) -> Optional[Dict[str, Any]]:
        """
        Get next transcript from the queue.

        Non-blocking. Returns None if queue is empty.

        Returns:
            Transcript dict with keys:
                - type: "interim" | "final"
                - text: Transcript text
                - is_final: Whether this is a final result
                - speech_final: Whether this ends the utterance
            or None if no transcript available
        """
        try:
            return self.transcript_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def close(self) -> None:
        """
        Close connection to Deepgram and cleanup resources.
        """
        logger.info("Closing Deepgram STT connection")

        self.is_connected = False

        # Cancel keepalive task
        if self.keepalive_task:
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except asyncio.CancelledError:
                pass

        # Close connection (synchronous call)
        if self.connection:
            try:
                self.connection.finish()
            except Exception as e:
                logger.error(f"Error closing Deepgram connection: {e}")

        # Clear transcript queue
        while not self.transcript_queue.empty():
            try:
                self.transcript_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.is_finals.clear()
        logger.info("Deepgram STT connection closed")

    # Event handlers
    # NOTE: These must be synchronous (not async) for Deepgram SDK v3.8.0

    def _on_open(self, *args, **kwargs) -> None:
        """Handle connection open event."""
        logger.info("Deepgram STT: Connected")

    def _on_transcript(self, *args, **kwargs) -> None:
        """
        Handle transcript event.

        Processes both interim and final transcripts:
        - Interim results: Used for barge-in detection (sent while AI is speaking)
        - Final results: Accumulated until speech_final or utterance_end
        - Speech final: Signals complete utterance, triggers LLM processing
        """
        # Extract result from args
        result = kwargs.get("result") or (args[1] if len(args) > 1 else args[0])

        # Get transcript text
        transcript = result.channel.alternatives[0].transcript

        if not transcript or transcript == "":
            return

        # Handle final results
        if result.is_final:
            self.is_finals.append(transcript)

            # Check if this is the end of the utterance
            if result.speech_final:
                # Combine all final transcripts into complete utterance
                utterance = " ".join(self.is_finals)
                self.is_finals.clear()

                logger.info(f"Deepgram STT: [Speech Final] {utterance}")

                # Add to queue for processing (use sync put_nowait)
                try:
                    self.transcript_queue.put_nowait(
                        {
                            "type": "final",
                            "text": utterance,
                            "is_final": True,
                            "speech_final": True,
                        }
                    )
                except asyncio.QueueFull:
                    logger.warning("Transcript queue full, dropping message")
            else:
                logger.debug(f"Deepgram STT: [Is Final] {transcript}")

                # Add to queue but not speech final (use sync put_nowait)
                try:
                    self.transcript_queue.put_nowait(
                        {
                            "type": "final",
                            "text": transcript,
                            "is_final": True,
                            "speech_final": False,
                        }
                    )
                except asyncio.QueueFull:
                    logger.warning("Transcript queue full, dropping message")
        else:
            # Interim results - used for barge-in detection
            logger.debug(f"Deepgram STT: [Interim Result] {transcript}")

            # Add to queue for barge-in detection (use sync put_nowait)
            try:
                self.transcript_queue.put_nowait(
                    {
                        "type": "interim",
                        "text": transcript,
                        "is_final": False,
                        "speech_final": False,
                    }
                )
            except asyncio.QueueFull:
                logger.warning("Transcript queue full, dropping interim result")

    def _on_utterance_end(self, *args, **kwargs) -> None:
        """
        Handle utterance end event.

        Backup mechanism to finalize utterance if speech_final not received.
        """
        if len(self.is_finals) > 0:
            logger.info("Deepgram STT: [Utterance End]")

            # Combine all final transcripts
            utterance = " ".join(self.is_finals)
            self.is_finals.clear()

            logger.info(f"Deepgram STT: [Speech Final via UtteranceEnd] {utterance}")

            # Add to queue (use sync put_nowait)
            try:
                self.transcript_queue.put_nowait(
                    {
                        "type": "final",
                        "text": utterance,
                        "is_final": True,
                        "speech_final": True,
                    }
                )
            except asyncio.QueueFull:
                logger.warning("Transcript queue full, dropping utterance end")

    def _on_close(self, *args, **kwargs) -> None:
        """Handle connection close event."""
        logger.info("Deepgram STT: Disconnected")
        self.is_connected = False

    def _on_error(self, *args, **kwargs) -> None:
        """Handle error event."""
        error = kwargs.get("error") or (args[1] if len(args) > 1 else args[0])
        logger.error(f"Deepgram STT: Error received: {error}")

    def _on_warning(self, *args, **kwargs) -> None:
        """Handle warning event."""
        warning = kwargs.get("warning") or (args[1] if len(args) > 1 else args[0])
        logger.warning(f"Deepgram STT: Warning received: {warning}")

    def _on_metadata(self, *args, **kwargs) -> None:
        """Handle metadata event."""
        metadata = kwargs.get("metadata") or (args[1] if len(args) > 1 else args[0])
        logger.debug(f"Deepgram STT: Metadata received: {metadata}")
