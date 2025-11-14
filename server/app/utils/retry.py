"""
Retry utilities with exponential backoff.

Provides retry logic for service connections with configurable
backoff strategies for resilient error recovery.
"""

import asyncio
import logging
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def with_retry(
    func: Callable[[], T],
    max_retries: int = 3,
    backoff_factor: float = 1.5,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    operation_name: Optional[str] = None
) -> T:
    """
    Retry an async operation with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Multiplier for delay between retries (default: 1.5)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        operation_name: Name for logging purposes

    Returns:
        Result from successful function call

    Raises:
        Exception: If all retries are exhausted

    Example:
        >>> result = await with_retry(
        ...     lambda: connect_to_service(),
        ...     max_retries=3,
        ...     operation_name="Service Connection"
        ... )
    """
    name = operation_name or func.__name__
    last_exception = None

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries}: {name}")
            result = await func()

            if attempt > 0:
                logger.info(f"✅ {name} succeeded on attempt {attempt + 1}/{max_retries}")

            return result

        except Exception as e:
            last_exception = e

            if attempt < max_retries - 1:
                # Calculate delay with exponential backoff
                delay = min(initial_delay * (backoff_factor ** attempt), max_delay)

                logger.warning(
                    f"⚠️  {name} failed (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                logger.info(f"Retrying in {delay:.1f}s...")

                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"❌ {name} failed after {max_retries} attempts: {str(e)}"
                )

    # All retries exhausted
    raise Exception(
        f"{name} failed after {max_retries} attempts. Last error: {str(last_exception)}"
    ) from last_exception


def sync_with_retry(
    func: Callable[[], T],
    max_retries: int = 3,
    backoff_factor: float = 1.5,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    operation_name: Optional[str] = None
) -> T:
    """
    Retry a synchronous operation with exponential backoff.

    Args:
        func: Synchronous function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Multiplier for delay between retries (default: 1.5)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        operation_name: Name for logging purposes

    Returns:
        Result from successful function call

    Raises:
        Exception: If all retries are exhausted
    """
    import time

    name = operation_name or func.__name__
    last_exception = None

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1}/{max_retries}: {name}")
            result = func()

            if attempt > 0:
                logger.info(f"✅ {name} succeeded on attempt {attempt + 1}/{max_retries}")

            return result

        except Exception as e:
            last_exception = e

            if attempt < max_retries - 1:
                # Calculate delay with exponential backoff
                delay = min(initial_delay * (backoff_factor ** attempt), max_delay)

                logger.warning(
                    f"⚠️  {name} failed (attempt {attempt + 1}/{max_retries}): {str(e)}"
                )
                logger.info(f"Retrying in {delay:.1f}s...")

                time.sleep(delay)
            else:
                logger.error(
                    f"❌ {name} failed after {max_retries} attempts: {str(e)}"
                )

    # All retries exhausted
    raise Exception(
        f"{name} failed after {max_retries} attempts. Last error: {str(last_exception)}"
    ) from last_exception
