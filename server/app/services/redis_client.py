"""Redis client for session and state management."""

import asyncio
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

# HIGH FIX: Timeout for Redis operations (2 seconds)
REDIS_TIMEOUT = 2.0

# CRITICAL FIX: Lua script for atomic session updates
# This prevents race conditions when multiple processes update the same session
UPDATE_SESSION_SCRIPT = """
local key = KEYS[1]
local ttl_key = KEYS[2]
local updates = cjson.decode(ARGV[1])
local timestamp = ARGV[2]

-- Get existing session
local current = redis.call('GET', key)
if not current then
    return nil
end

-- Parse existing session
local session = cjson.decode(current)

-- Apply updates
for k, v in pairs(updates) do
    session[k] = v
end

-- Update timestamp
session['last_updated'] = timestamp

-- Get current TTL
local ttl = redis.call('TTL', key)
if ttl <= 0 then
    ttl = 3600
end

-- Store updated session with TTL
redis.call('SETEX', key, ttl, cjson.encode(session))
return ttl
"""


async def init_redis():
    """Initialize Redis connection with connection pooling.

    Raises:
        Exception: If connection fails or cannot be validated
    """
    global redis_client
    try:
        redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,  # Connection pool size
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

        # CRITICAL FIX: Validate connection with ping
        await redis_client.ping()
        logger.info("Redis connection initialized and validated with connection pooling")

    except Exception as e:
        # CRITICAL FIX: Clean up and set redis_client to None on failure
        logger.error(f"Failed to initialize Redis connection: {e}")
        if redis_client:
            try:
                await redis_client.close()
            except:
                pass
        redis_client = None
        raise Exception(f"Redis connection initialization failed: {e}")


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

        # HIGH FIX: Add timeout to Redis operation
        try:
            await asyncio.wait_for(
                redis_client.setex(key, ttl, value),
                timeout=REDIS_TIMEOUT
            )
            logger.info(f"Session stored: {call_sid} (TTL: {ttl}s)")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout storing session {call_sid}")
            return False

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

        # HIGH FIX: Add timeout to Redis operation
        try:
            value = await asyncio.wait_for(
                redis_client.get(key),
                timeout=REDIS_TIMEOUT
            )

            if value:
                logger.info(f"Session cache hit: {call_sid}")
                return json.loads(value)
            else:
                logger.info(f"Session cache miss: {call_sid}")
                return None

        except asyncio.TimeoutError:
            logger.error(f"Timeout retrieving session {call_sid}")
            return None

    except Exception as e:
        logger.error(f"Error retrieving session {call_sid}: {e}")
        return None


async def update_session(call_sid: str, updates: dict) -> bool:
    """Update specific fields in an existing session using atomic Lua script.

    CRITICAL FIX: Uses Lua script to prevent race conditions during concurrent updates.
    This ensures atomic read-modify-write operations.

    Args:
        call_sid: Twilio call SID
        updates: Dictionary with fields to update

    Returns:
        True if successful, False otherwise
    """
    try:
        if not _check_redis_initialized():
            return False

        key = f"{SESSION_PREFIX}{call_sid}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # CRITICAL FIX: Use Lua script for atomic update
        # This replaces the get→update→set pattern that was vulnerable to race conditions
        # HIGH FIX: Add timeout to Redis operation
        try:
            result = await asyncio.wait_for(
                redis_client.eval(
                    UPDATE_SESSION_SCRIPT,
                    2,  # Number of keys
                    key,
                    key,  # ttl_key (not used but required for KEYS array)
                    json.dumps(updates),
                    timestamp
                ),
                timeout=REDIS_TIMEOUT
            )

            if result is None:
                logger.warning(f"Cannot update non-existent session: {call_sid}")
                return False

            logger.info(f"Session updated atomically: {call_sid}")
            return True

        except asyncio.TimeoutError:
            logger.error(f"Timeout updating session {call_sid}")
            return False

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

        # HIGH FIX: Add timeout to Redis operation
        try:
            deleted = await asyncio.wait_for(
                redis_client.delete(key),
                timeout=REDIS_TIMEOUT
            )

            if deleted:
                logger.info(f"Session deleted: {call_sid}")
                return True
            else:
                logger.warning(f"Session not found for deletion: {call_sid}")
                return False

        except asyncio.TimeoutError:
            logger.error(f"Timeout deleting session {call_sid}")
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

        # HIGH FIX: Add timeout to Redis operation
        try:
            await asyncio.wait_for(
                redis_client.setex(key, ttl, value),
                timeout=REDIS_TIMEOUT
            )
            logger.info(f"Customer cached: {phone} (TTL: {ttl}s)")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout caching customer {phone}")
            return False

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

        # HIGH FIX: Add timeout to Redis operation
        try:
            value = await asyncio.wait_for(
                redis_client.get(key),
                timeout=REDIS_TIMEOUT
            )

            if value:
                logger.info(f"Customer cache hit: {phone}")
                return json.loads(value)
            else:
                logger.info(f"Customer cache miss: {phone}")
                return None

        except asyncio.TimeoutError:
            logger.error(f"Timeout retrieving cached customer {phone}")
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

        # HIGH FIX: Add timeout to Redis operation
        try:
            deleted = await asyncio.wait_for(
                redis_client.delete(key),
                timeout=REDIS_TIMEOUT
            )

            if deleted:
                logger.info(f"Customer cache invalidated: {phone}")
                return True
            else:
                logger.info(f"Customer cache not found: {phone}")
                return False

        except asyncio.TimeoutError:
            logger.error(f"Timeout invalidating customer cache {phone}")
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

        # HIGH FIX: Add timeout to Redis ping operation
        try:
            await asyncio.wait_for(
                redis_client.ping(),
                timeout=REDIS_TIMEOUT
            )
            logger.debug("Redis health check: OK")
            return True
        except asyncio.TimeoutError:
            logger.error("Redis health check timed out")
            return False

    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False
