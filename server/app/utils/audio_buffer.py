"""
Audio buffering utility for efficient audio chunk processing.

Based on patterns from AdhamSamehA/Outbound-Phone-GPT for optimal
audio chunk sizes when sending to Deepgram STT.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    Buffer audio chunks for efficient transmission to Deepgram STT.

    Accumulates small audio chunks into larger buffers before sending,
    reducing the number of WebSocket messages and improving efficiency.

    Default buffer size: 3200 bytes (20 * 160 bytes)
    - Optimized for mulaw @ 8kHz phone audio
    - Balances latency vs efficiency
    """

    def __init__(self, buffer_size: int = 3200):
        """
        Initialize audio buffer.

        Args:
            buffer_size: Target size for buffered chunks in bytes (default: 3200)
        """
        self.buffer = bytearray()
        self.buffer_size = buffer_size
        logger.debug(f"AudioBuffer initialized with size: {buffer_size} bytes")

    def add(self, chunk: bytes) -> List[bytes]:
        """
        Add audio chunk to buffer and return complete buffers.

        Args:
            chunk: Audio data to add

        Returns:
            List of complete buffer chunks ready to send (may be empty)
        """
        self.buffer.extend(chunk)

        chunks_to_send = []
        while len(self.buffer) >= self.buffer_size:
            # Extract a complete buffer
            chunks_to_send.append(bytes(self.buffer[: self.buffer_size]))
            # Remove from buffer
            self.buffer = self.buffer[self.buffer_size :]

        if chunks_to_send:
            logger.debug(
                f"AudioBuffer: Sending {len(chunks_to_send)} chunk(s) of {self.buffer_size} bytes each"
            )

        return chunks_to_send

    def flush(self) -> Optional[bytes]:
        """
        Flush remaining buffer contents.

        Returns:
            Remaining buffer data, or None if empty
        """
        if self.buffer:
            chunk = bytes(self.buffer)
            self.buffer.clear()
            logger.debug(f"AudioBuffer: Flushing {len(chunk)} remaining bytes")
            return chunk
        return None

    def clear(self) -> None:
        """Clear the buffer without returning data."""
        if self.buffer:
            logger.debug(f"AudioBuffer: Clearing {len(self.buffer)} buffered bytes")
        self.buffer.clear()

    def size(self) -> int:
        """Get current buffer size in bytes."""
        return len(self.buffer)
