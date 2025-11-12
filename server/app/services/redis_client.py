"""Redis client for session and state management."""

import redis.asyncio as redis
from app.config import settings

redis_client = None


async def init_redis():
    """Initialize Redis connection."""
    global redis_client
    redis_client = await redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()


def get_redis():
    """Get Redis client."""
    return redis_client
