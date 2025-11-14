"""
Unit tests for PerformanceMetrics utility.

Tests timing tracking, metric collection, and reset behavior.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add server directory to path
server_path = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_path))

from app.utils.performance_metrics import PerformanceMetrics


def test_performance_metrics_initialization():
    """Test PerformanceMetrics initializes with correct defaults."""
    metrics = PerformanceMetrics()

    assert metrics.llm_start == 0
    assert metrics.tts_start == 0
    assert metrics.first_llm_token is True
    assert metrics.first_audio_byte is True
    assert metrics.metrics == {}


def test_start_llm():
    """Test starting LLM timing sets timestamp and flags."""
    metrics = PerformanceMetrics()

    before = time.time()
    metrics.start_llm()
    after = time.time()

    # Should have set timestamp
    assert before <= metrics.llm_start <= after
    assert metrics.first_llm_token is True


def test_track_llm_first_token():
    """Test tracking LLM first token records latency."""
    metrics = PerformanceMetrics()

    metrics.start_llm()
    time.sleep(0.01)  # Sleep 10ms
    metrics.track_llm_first_token()

    # Should have recorded metric
    assert 'llm_time_to_first_token_ms' in metrics.metrics
    # Should be at least 10ms (with some tolerance for timing)
    assert metrics.metrics['llm_time_to_first_token_ms'] >= 8.0
    # Flag should be false now
    assert metrics.first_llm_token is False


def test_track_llm_first_token_only_once():
    """Test that LLM first token is only tracked once."""
    metrics = PerformanceMetrics()

    metrics.start_llm()
    time.sleep(0.01)
    metrics.track_llm_first_token()
    first_value = metrics.metrics['llm_time_to_first_token_ms']

    # Try to track again
    time.sleep(0.01)
    metrics.track_llm_first_token()

    # Value should not change
    assert metrics.metrics['llm_time_to_first_token_ms'] == first_value


def test_track_llm_first_token_starts_tts_timing():
    """Test that tracking LLM first token starts TTS timing."""
    metrics = PerformanceMetrics()

    metrics.start_llm()
    time.sleep(0.01)

    # TTS start should be 0 before tracking
    assert metrics.tts_start == 0

    before = time.time()
    metrics.track_llm_first_token()
    after = time.time()

    # TTS start should now be set
    assert before <= metrics.tts_start <= after
    assert metrics.first_audio_byte is True


def test_track_tts_first_byte():
    """Test tracking TTS first byte records latency."""
    metrics = PerformanceMetrics()

    # Set up TTS timing
    metrics.start_llm()
    metrics.track_llm_first_token()

    time.sleep(0.01)  # Sleep 10ms
    metrics.track_tts_first_byte()

    # Should have recorded metric
    assert 'tts_time_to_first_byte_ms' in metrics.metrics
    assert metrics.metrics['tts_time_to_first_byte_ms'] >= 8.0
    # Flag should be false now
    assert metrics.first_audio_byte is False


def test_track_tts_first_byte_only_once():
    """Test that TTS first byte is only tracked once."""
    metrics = PerformanceMetrics()

    metrics.start_llm()
    metrics.track_llm_first_token()
    time.sleep(0.01)
    metrics.track_tts_first_byte()
    first_value = metrics.metrics['tts_time_to_first_byte_ms']

    # Try to track again
    time.sleep(0.01)
    metrics.track_tts_first_byte()

    # Value should not change
    assert metrics.metrics['tts_time_to_first_byte_ms'] == first_value


def test_track_overall_latency():
    """Test tracking overall response latency."""
    metrics = PerformanceMetrics()

    start_time = time.time()
    time.sleep(0.01)  # Sleep 10ms
    metrics.track_overall_latency(start_time)

    # Should have recorded metric
    assert 'overall_response_latency_ms' in metrics.metrics
    assert metrics.metrics['overall_response_latency_ms'] >= 8.0


def test_get_metrics():
    """Test get_metrics returns copy of metrics dict."""
    metrics = PerformanceMetrics()

    metrics.start_llm()
    metrics.track_llm_first_token()

    # Get metrics
    result = metrics.get_metrics()

    # Should be a copy
    assert result == metrics.metrics
    assert result is not metrics.metrics

    # Modifying result shouldn't affect original
    result['test'] = 123
    assert 'test' not in metrics.metrics


def test_reset():
    """Test reset clears all metrics and timestamps."""
    metrics = PerformanceMetrics()

    # Set up some metrics
    metrics.start_llm()
    metrics.track_llm_first_token()
    time.sleep(0.01)
    metrics.track_tts_first_byte()

    # Verify we have data
    assert metrics.llm_start > 0
    assert metrics.tts_start > 0
    assert metrics.first_llm_token is False
    assert metrics.first_audio_byte is False
    assert len(metrics.metrics) > 0

    # Reset
    metrics.reset()

    # Should be back to initial state
    assert metrics.llm_start == 0
    assert metrics.tts_start == 0
    assert metrics.first_llm_token is True
    assert metrics.first_audio_byte is True
    assert metrics.metrics == {}


def test_reset_clears_metrics_dict():
    """Test that reset properly clears the metrics dictionary."""
    metrics = PerformanceMetrics()

    # Add several metrics
    metrics.start_llm()
    metrics.track_llm_first_token()
    metrics.track_tts_first_byte()
    metrics.track_overall_latency(time.time())

    # Should have 3 metrics
    assert len(metrics.metrics) == 3

    # Reset
    metrics.reset()

    # Dict should be empty
    assert metrics.metrics == {}
    assert len(metrics.metrics) == 0


def test_multiple_tracking_cycles():
    """Test multiple complete cycles of metric tracking."""
    metrics = PerformanceMetrics()

    # First cycle
    metrics.start_llm()
    time.sleep(0.005)
    metrics.track_llm_first_token()
    time.sleep(0.005)
    metrics.track_tts_first_byte()

    first_llm = metrics.metrics['llm_time_to_first_token_ms']
    first_tts = metrics.metrics['tts_time_to_first_byte_ms']

    # Reset for second cycle
    metrics.reset()

    # Second cycle
    metrics.start_llm()
    time.sleep(0.010)  # Different timing
    metrics.track_llm_first_token()
    time.sleep(0.010)
    metrics.track_tts_first_byte()

    second_llm = metrics.metrics['llm_time_to_first_token_ms']
    second_tts = metrics.metrics['tts_time_to_first_byte_ms']

    # Second cycle should have different (higher) values
    assert second_llm > first_llm
    assert second_tts > first_tts


def test_track_without_start_does_nothing():
    """Test that tracking without start_llm does nothing."""
    metrics = PerformanceMetrics()

    # Try to track without starting
    metrics.track_llm_first_token()

    # Should not have recorded anything
    assert 'llm_time_to_first_token_ms' not in metrics.metrics


def test_track_tts_without_llm_does_nothing():
    """Test that tracking TTS without LLM first token does nothing."""
    metrics = PerformanceMetrics()

    # Try to track TTS without LLM
    metrics.track_tts_first_byte()

    # Should not have recorded anything
    assert 'tts_time_to_first_byte_ms' not in metrics.metrics


def test_track_overall_with_zero_start_does_nothing():
    """Test that tracking overall with zero start_time does nothing."""
    metrics = PerformanceMetrics()

    # Try to track with 0 start time
    metrics.track_overall_latency(0)

    # Should not have recorded anything
    assert 'overall_response_latency_ms' not in metrics.metrics


def test_metric_values_are_positive():
    """Test that all metric values are positive numbers."""
    metrics = PerformanceMetrics()

    metrics.start_llm()
    time.sleep(0.001)
    metrics.track_llm_first_token()
    time.sleep(0.001)
    metrics.track_tts_first_byte()
    metrics.track_overall_latency(time.time() - 0.005)

    # All metrics should be positive
    for key, value in metrics.metrics.items():
        assert value > 0, f"{key} should be positive"


def test_realistic_voice_agent_workflow():
    """Test realistic voice agent workflow with timing."""
    metrics = PerformanceMetrics()

    # User speaks -> start LLM processing
    metrics.start_llm()

    # Simulate LLM latency (100ms)
    time.sleep(0.1)

    # First token from LLM
    metrics.track_llm_first_token()
    assert 'llm_time_to_first_token_ms' in metrics.metrics
    assert metrics.metrics['llm_time_to_first_token_ms'] >= 95.0

    # Simulate TTS latency (50ms)
    time.sleep(0.05)

    # First audio byte from TTS
    metrics.track_tts_first_byte()
    assert 'tts_time_to_first_byte_ms' in metrics.metrics
    assert metrics.metrics['tts_time_to_first_byte_ms'] >= 45.0

    # Get metrics summary
    result = metrics.get_metrics()
    assert len(result) == 2

    # Reset for next turn
    metrics.reset()
    assert len(metrics.metrics) == 0


if __name__ == "__main__":
    # Run all tests
    import pytest
    pytest.main([__file__, "-v"])
