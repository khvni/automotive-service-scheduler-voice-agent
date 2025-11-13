"""
Call logging utility for tracking voice call events, transcripts, and metrics.

This module provides functions to log call events to database and Redis
for analytics, debugging, and performance monitoring.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.models.call_log import CallLog
from app.services.redis_client import update_session
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_call_event(
    db: AsyncSession,
    call_sid: str,
    event_type: str,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Log a call event to database and Redis.

    Args:
        db: Database session
        call_sid: Twilio call SID
        event_type: Event type (e.g., "call_started", "transcript", "tool_executed")
        data: Event data
        metadata: Optional metadata (latency, token count, etc.)

    Returns:
        True if logged successfully, False otherwise

    Event Types:
        - call_started: Call initiated
        - call_ended: Call completed
        - transcript: User or assistant message
        - tool_executed: Tool/function executed
        - barge_in: User interrupted AI
        - error: Error occurred
    """
    try:
        # Log to database (CallLog table)
        # Note: This is a simplified version. Feature 9 will add comprehensive logging.

        # Log to Redis session for real-time tracking
        await update_session(
            call_sid,
            {
                f"last_event_{event_type}": datetime.now(timezone.utc).isoformat(),
                f"event_data_{event_type}": data,
            },
        )

        logger.info(f"Call event logged: {event_type} for call {call_sid}")
        return True

    except Exception as e:
        logger.error(f"Error logging call event: {e}", exc_info=True)
        return False


async def log_transcript(
    call_sid: str, role: str, content: str, timestamp: Optional[datetime] = None
) -> bool:
    """
    Log a transcript message (user or assistant).

    Args:
        call_sid: Twilio call SID
        role: "user" or "assistant"
        content: Message content
        timestamp: Optional timestamp (defaults to now)

    Returns:
        True if logged successfully
    """
    try:
        timestamp = timestamp or datetime.now(timezone.utc)

        await update_session(
            call_sid,
            {
                "last_transcript": {
                    "role": role,
                    "content": content,
                    "timestamp": timestamp.isoformat(),
                }
            },
        )

        logger.debug(f"Transcript logged for call {call_sid}: {role}")
        return True

    except Exception as e:
        logger.error(f"Error logging transcript: {e}")
        return False


async def log_performance_metric(
    call_sid: str, metric_name: str, value: float, unit: str = "ms"
) -> bool:
    """
    Log a performance metric.

    Args:
        call_sid: Twilio call SID
        metric_name: Metric name (e.g., "stt_latency", "llm_latency", "tts_latency")
        value: Metric value
        unit: Unit of measurement (default: "ms")

    Returns:
        True if logged successfully
    """
    try:
        await update_session(
            call_sid,
            {
                f"metric_{metric_name}": value,
                f"metric_{metric_name}_unit": unit,
            },
        )

        logger.debug(f"Performance metric logged: {metric_name}={value}{unit}")
        return True

    except Exception as e:
        logger.error(f"Error logging performance metric: {e}")
        return False


async def finalize_call_log(
    db: AsyncSession,
    call_sid: str,
    total_duration: float,
    conversation_history: list,
    token_usage: Dict[str, int],
) -> bool:
    """
    Finalize call log with summary data.

    Args:
        db: Database session
        call_sid: Twilio call SID
        total_duration: Total call duration in seconds
        conversation_history: Full conversation history
        token_usage: Token usage statistics

    Returns:
        True if logged successfully
    """
    try:
        # TODO: Implement database insertion for CallLog table
        # For now, just update Redis with final summary

        await update_session(
            call_sid,
            {
                "total_duration": total_duration,
                "total_messages": len(conversation_history),
                "total_tokens": token_usage.get("total_tokens", 0),
                "finalized_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            f"Call log finalized for {call_sid}: {total_duration}s, {len(conversation_history)} messages"
        )
        return True

    except Exception as e:
        logger.error(f"Error finalizing call log: {e}", exc_info=True)
        return False
