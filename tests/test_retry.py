"""
Unit tests for Retry utilities.

Tests async and sync retry logic with exponential backoff.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add server directory to path
server_path = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_path))

from app.utils.retry import with_retry, sync_with_retry


# Test async retry

async def async_succeeds_immediately():
    """Async function that succeeds immediately."""
    return "success"


async def async_fails_then_succeeds(attempts_before_success: int):
    """Async function that fails N times then succeeds."""
    if not hasattr(async_fails_then_succeeds, 'call_count'):
        async_fails_then_succeeds.call_count = {}

    key = id(async_fails_then_succeeds)
    async_fails_then_succeeds.call_count[key] = async_fails_then_succeeds.call_count.get(key, 0) + 1

    if async_fails_then_succeeds.call_count[key] <= attempts_before_success:
        raise Exception(f"Attempt {async_fails_then_succeeds.call_count[key]} failed")

    return "success"


async def async_always_fails():
    """Async function that always fails."""
    raise Exception("Always fails")


def test_with_retry_succeeds_immediately():
    """Test with_retry with immediately successful function."""
    async def run():
        result = await with_retry(async_succeeds_immediately, max_retries=3)
        assert result == "success"

    asyncio.run(run())


def test_with_retry_succeeds_after_failures():
    """Test with_retry succeeds after initial failures."""
    async def run():
        # Reset call count
        if hasattr(async_fails_then_succeeds, 'call_count'):
            async_fails_then_succeeds.call_count.clear()

        # Fails 2 times, succeeds on 3rd
        result = await with_retry(
            lambda: async_fails_then_succeeds(2),
            max_retries=3
        )
        assert result == "success"

    asyncio.run(run())


def test_with_retry_exhausts_retries():
    """Test with_retry raises after exhausting retries."""
    async def run():
        try:
            await with_retry(async_always_fails, max_retries=3)
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Always fails" in str(e)

    asyncio.run(run())


def test_with_retry_exponential_backoff():
    """Test with_retry uses exponential backoff."""
    async def run():
        # Reset call count
        if hasattr(async_fails_then_succeeds, 'call_count'):
            async_fails_then_succeeds.call_count.clear()

        start_time = time.time()

        # Fails 2 times, succeeds on 3rd
        # Should have delays: 1.0s, 1.5s
        await with_retry(
            lambda: async_fails_then_succeeds(2),
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=1.5
        )

        elapsed = time.time() - start_time

        # Should take at least 2.5 seconds (1.0 + 1.5)
        assert elapsed >= 2.4, f"Expected >=2.4s, got {elapsed:.2f}s"

    asyncio.run(run())


def test_with_retry_respects_max_delay():
    """Test with_retry respects max_delay cap."""
    async def run():
        # Reset call count
        if hasattr(async_fails_then_succeeds, 'call_count'):
            async_fails_then_succeeds.call_count.clear()

        start_time = time.time()

        # Fails 3 times, succeeds on 4th
        # Delays would be: 1.0, 3.0, 9.0
        # But max_delay=2.0, so: 1.0, 2.0, 2.0
        await with_retry(
            lambda: async_fails_then_succeeds(3),
            max_retries=4,
            initial_delay=1.0,
            backoff_factor=3.0,
            max_delay=2.0
        )

        elapsed = time.time() - start_time

        # Should take around 5 seconds (1.0 + 2.0 + 2.0)
        assert 4.8 <= elapsed <= 6.0, f"Expected ~5.0s, got {elapsed:.2f}s"

    asyncio.run(run())


# Test sync retry

def sync_succeeds_immediately():
    """Sync function that succeeds immediately."""
    return "success"


def sync_fails_then_succeeds(attempts_before_success: int):
    """Sync function that fails N times then succeeds."""
    if not hasattr(sync_fails_then_succeeds, 'call_count'):
        sync_fails_then_succeeds.call_count = {}

    key = id(sync_fails_then_succeeds)
    sync_fails_then_succeeds.call_count[key] = sync_fails_then_succeeds.call_count.get(key, 0) + 1

    if sync_fails_then_succeeds.call_count[key] <= attempts_before_success:
        raise Exception(f"Attempt {sync_fails_then_succeeds.call_count[key]} failed")

    return "success"


def sync_always_fails():
    """Sync function that always fails."""
    raise Exception("Always fails")


def test_sync_with_retry_succeeds_immediately():
    """Test sync_with_retry with immediately successful function."""
    result = sync_with_retry(sync_succeeds_immediately, max_retries=3)
    assert result == "success"


def test_sync_with_retry_succeeds_after_failures():
    """Test sync_with_retry succeeds after initial failures."""
    # Reset call count
    if hasattr(sync_fails_then_succeeds, 'call_count'):
        sync_fails_then_succeeds.call_count.clear()

    # Fails 2 times, succeeds on 3rd
    result = sync_with_retry(
        lambda: sync_fails_then_succeeds(2),
        max_retries=3
    )
    assert result == "success"


def test_sync_with_retry_exhausts_retries():
    """Test sync_with_retry raises after exhausting retries."""
    try:
        sync_with_retry(sync_always_fails, max_retries=3)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Always fails" in str(e)


def test_sync_with_retry_exponential_backoff():
    """Test sync_with_retry uses exponential backoff."""
    # Reset call count
    if hasattr(sync_fails_then_succeeds, 'call_count'):
        sync_fails_then_succeeds.call_count.clear()

    start_time = time.time()

    # Fails 2 times, succeeds on 3rd
    # Should have delays: 0.5s, 0.75s
    sync_with_retry(
        lambda: sync_fails_then_succeeds(2),
        max_retries=3,
        initial_delay=0.5,
        backoff_factor=1.5
    )

    elapsed = time.time() - start_time

    # Should take at least 1.25 seconds (0.5 + 0.75)
    assert elapsed >= 1.2, f"Expected >=1.2s, got {elapsed:.2f}s"


def test_sync_with_retry_respects_max_delay():
    """Test sync_with_retry respects max_delay cap."""
    # Reset call count
    if hasattr(sync_fails_then_succeeds, 'call_count'):
        sync_fails_then_succeeds.call_count.clear()

    start_time = time.time()

    # Fails 3 times, succeeds on 4th
    # Delays would be: 0.5, 1.5, 4.5
    # But max_delay=1.0, so: 0.5, 1.0, 1.0
    sync_with_retry(
        lambda: sync_fails_then_succeeds(3),
        max_retries=4,
        initial_delay=0.5,
        backoff_factor=3.0,
        max_delay=1.0
    )

    elapsed = time.time() - start_time

    # Should take around 2.5 seconds (0.5 + 1.0 + 1.0)
    assert 2.4 <= elapsed <= 3.0, f"Expected ~2.5s, got {elapsed:.2f}s"


def test_with_retry_preserves_exception_chain():
    """Test that with_retry preserves exception chain."""
    async def run():
        try:
            await with_retry(async_always_fails, max_retries=2)
        except Exception as e:
            # Should have __cause__ set
            assert e.__cause__ is not None
            assert "Always fails" in str(e.__cause__)

    asyncio.run(run())


def test_sync_with_retry_preserves_exception_chain():
    """Test that sync_with_retry preserves exception chain."""
    try:
        sync_with_retry(sync_always_fails, max_retries=2)
    except Exception as e:
        # Should have __cause__ set
        assert e.__cause__ is not None
        assert "Always fails" in str(e.__cause__)


def test_with_retry_default_parameters():
    """Test with_retry with default parameters."""
    async def run():
        result = await with_retry(async_succeeds_immediately)
        assert result == "success"

    asyncio.run(run())


def test_sync_with_retry_default_parameters():
    """Test sync_with_retry with default parameters."""
    result = sync_with_retry(sync_succeeds_immediately)
    assert result == "success"


if __name__ == "__main__":
    # Run all tests
    import pytest
    pytest.main([__file__, "-v"])
