"""
Abstract base class for Text-to-Speech services.

This interface enables swapping between different TTS providers
(Deepgram, ElevenLabs, Cartesia, etc.) with consistent API.
"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio


class TTSInterface(ABC):
    """
    Abstract interface for Text-to-Speech services.

    Defines the contract that all TTS implementations must follow,
    enabling easy provider swapping while maintaining consistent behavior.
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to TTS service.

        Should set up WebSocket connection, event handlers,
        and any necessary initialization.

        Raises:
            Exception: If connection fails
        """
        pass

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """
        Send text to be converted to speech.

        Text is streamed chunk by chunk for low-latency synthesis.
        Multiple calls can be made before flush() for streaming.

        Args:
            text: Text chunk to synthesize

        Raises:
            Exception: If not connected or send fails
        """
        pass

    @abstractmethod
    async def flush(self) -> None:
        """
        Signal end of text stream and flush remaining audio.

        Tells TTS service that no more text is coming, allowing
        it to finalize and return any remaining audio.
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """
        Clear audio queue and stop current synthesis (barge-in).

        Used when user interrupts AI speech. Clears pending audio
        and stops current playback to enable immediate response.
        """
        pass

    @abstractmethod
    async def get_audio(self) -> Optional[bytes]:
        """
        Get next audio chunk from the queue.

        Non-blocking. Returns None if no audio available.
        Audio is typically in format specified at connection
        (e.g., mulaw @ 8kHz for Twilio).

        Returns:
            Audio bytes or None if queue is empty
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection and cleanup resources.

        Should gracefully close WebSocket, cancel tasks,
        clear queues, and release resources.
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to TTS service.

        Returns:
            True if connected, False otherwise
        """
        pass
