"""
Unit tests for AudioBuffer utility.

Tests buffering logic, edge cases, and flush behavior.
"""

import sys
from pathlib import Path

# Add server directory to path
server_path = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_path))

from app.utils.audio_buffer import AudioBuffer


def test_audio_buffer_initialization():
    """Test AudioBuffer initializes with correct buffer size."""
    buffer = AudioBuffer(buffer_size=3200)
    assert buffer.buffer_size == 3200
    assert buffer.size() == 0


def test_audio_buffer_default_size():
    """Test AudioBuffer uses default size when not specified."""
    buffer = AudioBuffer()
    assert buffer.buffer_size == 3200  # Default from class


def test_audio_buffer_accumulates_until_threshold():
    """Test that buffer accumulates data until reaching buffer_size."""
    buffer = AudioBuffer(buffer_size=100)

    # Add 50 bytes - should not return anything
    result = buffer.add(b"x" * 50)
    assert result == []
    assert buffer.size() == 50

    # Add 30 bytes - still under threshold
    result = buffer.add(b"y" * 30)
    assert result == []
    assert buffer.size() == 80


def test_audio_buffer_returns_complete_chunk():
    """Test that buffer returns complete chunk when threshold reached."""
    buffer = AudioBuffer(buffer_size=100)

    # Add 120 bytes - should return 1 chunk of 100, keep 20
    result = buffer.add(b"a" * 120)
    assert len(result) == 1
    assert len(result[0]) == 100
    assert result[0] == b"a" * 100
    assert buffer.size() == 20


def test_audio_buffer_returns_multiple_chunks():
    """Test that buffer returns multiple chunks when enough data."""
    buffer = AudioBuffer(buffer_size=100)

    # Add 350 bytes - should return 3 chunks of 100, keep 50
    result = buffer.add(b"b" * 350)
    assert len(result) == 3
    assert all(len(chunk) == 100 for chunk in result)
    assert all(chunk == b"b" * 100 for chunk in result)
    assert buffer.size() == 50


def test_audio_buffer_flush_returns_remaining():
    """Test that flush returns remaining buffered data."""
    buffer = AudioBuffer(buffer_size=100)

    # Add 75 bytes
    buffer.add(b"c" * 75)
    assert buffer.size() == 75

    # Flush should return the 75 bytes
    flushed = buffer.flush()
    assert len(flushed) == 75
    assert flushed == b"c" * 75
    assert buffer.size() == 0


def test_audio_buffer_flush_empty_buffer():
    """Test that flush on empty buffer returns None."""
    buffer = AudioBuffer(buffer_size=100)

    flushed = buffer.flush()
    assert flushed is None
    assert buffer.size() == 0


def test_audio_buffer_clear():
    """Test that clear removes all buffered data."""
    buffer = AudioBuffer(buffer_size=100)

    # Add some data
    buffer.add(b"d" * 75)
    assert buffer.size() == 75

    # Clear should empty the buffer
    buffer.clear()
    assert buffer.size() == 0


def test_audio_buffer_clear_then_add():
    """Test that buffer works correctly after clear."""
    buffer = AudioBuffer(buffer_size=100)

    # Add data, then clear
    buffer.add(b"e" * 75)
    buffer.clear()

    # Add new data - should work normally
    result = buffer.add(b"f" * 120)
    assert len(result) == 1
    assert result[0] == b"f" * 100
    assert buffer.size() == 20


def test_audio_buffer_exact_buffer_size():
    """Test behavior when adding exactly buffer_size bytes."""
    buffer = AudioBuffer(buffer_size=100)

    # Add exactly 100 bytes
    result = buffer.add(b"g" * 100)
    assert len(result) == 1
    assert len(result[0]) == 100
    assert buffer.size() == 0


def test_audio_buffer_empty_input():
    """Test that adding empty bytes doesn't affect buffer."""
    buffer = AudioBuffer(buffer_size=100)

    result = buffer.add(b"")
    assert result == []
    assert buffer.size() == 0


def test_audio_buffer_sequential_adds():
    """Test sequential adds that cross threshold."""
    buffer = AudioBuffer(buffer_size=100)

    # Add 60 bytes
    result1 = buffer.add(b"h" * 60)
    assert result1 == []
    assert buffer.size() == 60

    # Add 30 bytes (90 total)
    result2 = buffer.add(b"h" * 30)
    assert result2 == []
    assert buffer.size() == 90

    # Add 50 bytes (140 total) - should return 1 chunk, keep 40
    result3 = buffer.add(b"h" * 50)
    assert len(result3) == 1
    assert len(result3[0]) == 100
    assert buffer.size() == 40


def test_audio_buffer_optimal_twilio_size():
    """Test buffer with optimal Twilio mulaw size (3200 bytes)."""
    buffer = AudioBuffer(buffer_size=3200)

    # Simulate Twilio sending 160-byte chunks (20ms of mulaw @ 8kHz)
    twilio_chunk_size = 160
    chunks = []

    # Send 21 chunks (3360 bytes total)
    for _ in range(21):
        result = buffer.add(b"x" * twilio_chunk_size)
        chunks.extend(result)

    # Should have returned 1 complete chunk of 3200
    assert len(chunks) == 1
    assert len(chunks[0]) == 3200

    # Should have 160 bytes remaining (3360 - 3200)
    assert buffer.size() == 160


def test_audio_buffer_flush_after_complete_chunk():
    """Test that flush after complete chunk returns None."""
    buffer = AudioBuffer(buffer_size=100)

    # Add exactly 100 bytes (returns complete chunk)
    result = buffer.add(b"i" * 100)
    assert len(result) == 1

    # Flush should return None since buffer is empty
    flushed = buffer.flush()
    assert flushed is None


def test_audio_buffer_mixed_operations():
    """Test mixed sequence of operations."""
    buffer = AudioBuffer(buffer_size=100)

    # Add 50
    buffer.add(b"j" * 50)
    assert buffer.size() == 50

    # Clear
    buffer.clear()
    assert buffer.size() == 0

    # Add 80
    buffer.add(b"k" * 80)
    assert buffer.size() == 80

    # Flush
    flushed = buffer.flush()
    assert len(flushed) == 80
    assert buffer.size() == 0

    # Add 200 (returns 2 chunks)
    result = buffer.add(b"l" * 200)
    assert len(result) == 2
    assert buffer.size() == 0


if __name__ == "__main__":
    # Run all tests
    import pytest
    pytest.main([__file__, "-v"])
