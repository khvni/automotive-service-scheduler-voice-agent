"""Redis client for session and state management."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

redis_client: Optional[redis.Redis] = None

# Key prefixes for namespace organization
SESSION_PREFIX = "session:"
CUSTOMER_PREFIX = "customer:"


async def init_redis():
    """Initialize Redis connection with connection pooling."""
    global redis_client
    redis_client = await redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,  # Connection pool size
        socket_connect_timeout=5,
        socket_keepalive=True,
    )
    logger.info("Redis connection initialized with connection pooling")


async def close_redis():
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")


def _check_redis_initialized() -> bool:
    """Check if Redis client is initialized."""
    if not redis_client:
        logger.error("Redis client not initialized - call init_redis() first")
        return False
    return True


def get_redis():
    """Get Redis client instance.

    Returns:
        Redis client instance or None if not initialized.
    """
    return redis_client


# ============================================================================
# Session Management Functions
# ============================================================================


async def set_session(call_sid: str, session_data: dict, ttl: int = 3600) -> bool:
    """Store session state for an active call.

    Args:
        call_sid: Twilio call SID (unique identifier for the call)
        session_data: Dictionary containing session data
        ttl: Time-to-live in seconds (default: 3600 = 1 hour)

    Returns:
        True if successful, False otherwise

    Session data structure:
        {
            "call_sid": str,
            "stream_sid": str,
            "caller_phone": str,
            "customer_id": int | None,
            "conversation_history": [
                {"role": "user"|"assistant"|"function", "content": str, "timestamp": str}
            ],
            "current_state": str,  # e.g., "greeting", "collecting_info", "booking"
            "collected_data": {},  # Slots collected during conversation
            "intent": str | None,
            "speaking": bool,
            "created_at": str,
            "last_updated": str
        }
    """
    try:
        if not _check_redis_initialized():
            return False

        key = f"{SESSION_PREFIX}{call_sid}"

        # Add metadata timestamps
        session_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        if "created_at" not in session_data:
            session_data["created_at"] = session_data["last_updated"]

        # Serialize to JSON
        value = json.dumps(session_data)

        # Store with TTL
        await redis_client.setex(key, ttl, value)
        logger.info(f"Session stored: {call_sid} (TTL: {ttl}s)")
        return True

    except Exception as e:
        logger.error(f"Error storing session {call_sid}: {e}")
        return False


async def get_session(call_sid: str) -> Optional[dict]:
    """Retrieve session state for an active call.

    Args:
        call_sid: Twilio call SID

    Returns:
        Session data dictionary or None if not found
    """
    try:
        if not _check_redis_initialized():
            return None

        key = f"{SESSION_PREFIX}{call_sid}"
        value = await redis_client.get(key)

        if value:
            logger.info(f"Session cache hit: {call_sid}")
            return json.loads(value)
        else:
            logger.info(f"Session cache miss: {call_sid}")
            return None

    except Exception as e:
        logger.error(f"Error retrieving session {call_sid}: {e}")
        return None


async def update_session(call_sid: str, updates: dict) -> bool:
    """Update specific fields in an existing session.

    Args:
        call_sid: Twilio call SID
        updates: Dictionary with fields to update

    Returns:
        True if successful, False otherwise
    """
    try:
        if not _check_redis_initialized():
            return False

        # Get existing session
        session_data = await get_session(call_sid)
        if not session_data:
            logger.warning(f"Cannot update non-existent session: {call_sid}")
            return False

        # Get remaining TTL
        key = f"{SESSION_PREFIX}{call_sid}"
        ttl = await redis_client.ttl(key)
        if ttl <= 0:
            ttl = 3600  # Default if TTL expired or key doesn't exist

        # Merge updates
        session_data.update(updates)
        session_data["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Store updated session with original TTL
        return await set_session(call_sid, session_data, ttl)

    except Exception as e:
        logger.error(f"Error updating session {call_sid}: {e}")
        return False


async def delete_session(call_sid: str) -> bool:
    """Clean up session data when call ends.

    Args:
        call_sid: Twilio call SID

    Returns:
        True if deleted, False otherwise
    """
    try:
        if not _check_redis_initialized():
            return False

        key = f"{SESSION_PREFIX}{call_sid}"
        deleted = await redis_client.delete(key)

        if deleted:
            logger.info(f"Session deleted: {call_sid}")
            return True
        else:
            logger.warning(f"Session not found for deletion: {call_sid}")
            return False

    except Exception as e:
        logger.error(f"Error deleting session {call_sid}: {e}")
        return False


# ============================================================================
# Customer Caching Functions
# ============================================================================


async def cache_customer(phone: str, customer_data: dict, ttl: int = 300) -> bool:
    """Cache customer data to reduce database queries.

    Args:
        phone: Customer phone number (normalized)
        customer_data: Dictionary containing customer data
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)

    Returns:
        True if successful, False otherwise

    Customer cache structure:
        {
            "id": int,
            "phone_number": str,
            "first_name": str,
            "last_name": str,
            "email": str,
            "vehicles": [...],
            "upcoming_appointments": [...],
            "last_service_date": str | None,
            "cached_at": str
        }
    """
    try:
        if not _check_redis_initialized():
            return False

        key = f"{CUSTOMER_PREFIX}{phone}"

        # Add cache timestamp
        customer_data["cached_at"] = datetime.now(timezone.utc).isoformat()

        # Serialize to JSON
        value = json.dumps(customer_data)

        # Store with TTL (5 minutes default for frequently changing data)
        await redis_client.setex(key, ttl, value)
        logger.info(f"Customer cached: {phone} (TTL: {ttl}s)")
        return True

    except Exception as e:
        logger.error(f"Error caching customer {phone}: {e}")
        return False


async def get_cached_customer(phone: str) -> Optional[dict]:
    """Retrieve cached customer data.

    Args:
        phone: Customer phone number

    Returns:
        Customer data dictionary or None if not found
    """
    try:
        if not _check_redis_initialized():
            return None

        key = f"{CUSTOMER_PREFIX}{phone}"
        value = await redis_client.get(key)

        if value:
            logger.info(f"Customer cache hit: {phone}")
            return json.loads(value)
        else:
            logger.info(f"Customer cache miss: {phone}")
            return None

    except Exception as e:
        logger.error(f"Error retrieving cached customer {phone}: {e}")
        return None


async def invalidate_customer_cache(phone: str) -> bool:
    """Clear customer cache (e.g., after data update).

    Args:
        phone: Customer phone number

    Returns:
        True if deleted, False otherwise
    """
    try:
        if not _check_redis_initialized():
            return False

        key = f"{CUSTOMER_PREFIX}{phone}"
        deleted = await redis_client.delete(key)

        if deleted:
            logger.info(f"Customer cache invalidated: {phone}")
            return True
        else:
            logger.info(f"Customer cache not found: {phone}")
            return False

    except Exception as e:
        logger.error(f"Error invalidating customer cache {phone}: {e}")
        return False


# ============================================================================
# Health Check
# ============================================================================


async def check_redis_health() -> bool:
    """Test Redis connectivity.

    Returns:
        True if Redis is accessible, False otherwise
    """
    try:
        if not redis_client:
            logger.error("Redis client not initialized")
            return False

        # Ping Redis
        await redis_client.ping()
        logger.debug("Redis health check: OK")
        return True

    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False
