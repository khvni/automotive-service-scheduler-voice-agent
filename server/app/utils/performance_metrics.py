"""
Performance metrics tracking for voice agent.

Tracks latency metrics for debugging and optimization:
- STT → LLM latency
- LLM Time to First Token
- TTS Time to First Byte
- Overall response latency
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """
    Track performance metrics for voice agent pipeline.

    Based on patterns from deepgram/deepgram-twilio-streaming-voice-agent
    to enable debugging and optimization of real-time voice interactions.
    """

    def __init__(self):
        """Initialize performance metric trackers."""
        # Timestamps
        self.llm_start: float = 0
        self.tts_start: float = 0

        # Flags
        self.first_llm_token: bool = True
        self.first_audio_byte: bool = True

        # Metrics storage
        self.metrics: dict = {}

    def start_llm(self) -> None:
        """Mark the start of LLM processing."""
        self.llm_start = time.time()
        self.first_llm_token = True
        logger.debug("LLM processing started")

    def track_llm_first_token(self) -> None:
        """Track time to first token from LLM."""
        if self.first_llm_token and self.llm_start > 0:
            duration_ms = (time.time() - self.llm_start) * 1000
            self.metrics['llm_time_to_first_token_ms'] = duration_ms
            logger.info(f"⚡ LLM Time to First Token: {duration_ms:.2f}ms")
            self.first_llm_token = False

            # Start TTS timing
            self.tts_start = time.time()
            self.first_audio_byte = True

    def track_tts_first_byte(self) -> None:
        """Track time to first audio byte from TTS."""
        if self.first_audio_byte and self.tts_start > 0:
            duration_ms = (time.time() - self.tts_start) * 1000
            self.metrics['tts_time_to_first_byte_ms'] = duration_ms
            logger.info(f"🎵 TTS Time to First Byte: {duration_ms:.2f}ms")
            self.first_audio_byte = False

    def track_overall_latency(self, start_time: float) -> None:
        """Track overall response latency from user speech to audio playback."""
        if start_time > 0:
            duration_ms = (time.time() - start_time) * 1000
            self.metrics['overall_response_latency_ms'] = duration_ms
            logger.info(f"📊 Overall Response Latency: {duration_ms:.2f}ms")

    def reset(self) -> None:
        """Reset all metrics for next interaction."""
        self.llm_start = 0
        self.tts_start = 0
        self.first_llm_token = True
        self.first_audio_byte = True

    def get_metrics(self) -> dict:
        """Get current metrics."""
        return self.metrics.copy()

    def log_summary(self) -> None:
        """Log a summary of all collected metrics."""
        if self.metrics:
            logger.info("=== Performance Metrics Summary ===")
            for key, value in self.metrics.items():
                logger.info(f"  {key}: {value:.2f}ms")
            logger.info("=" * 35)
