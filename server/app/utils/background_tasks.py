"""
Background tasks for periodic monitoring and maintenance.

Simple background tasks for logging metrics and health checks.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def log_calendar_metrics_periodically(interval_seconds: int = 3600):
    """
    Log calendar metrics summary periodically.

    Args:
        interval_seconds: How often to log metrics (default: 3600 = 1 hour)

    This task runs in the background and logs calendar operation metrics
    at regular intervals for monitoring and debugging.
    """
    from app.utils.calendar_metrics import get_metrics_tracker

    logger.info(f"Starting periodic calendar metrics logging (every {interval_seconds}s)")

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            tracker = get_metrics_tracker()

            # Log summary
            logger.info("=" * 60)
            logger.info("📊 PERIODIC CALENDAR METRICS SUMMARY")
            logger.info("=" * 60)

            overall_stats = tracker.get_stats()

            if overall_stats["total_operations"] > 0:
                logger.info(
                    f"Total Operations: {overall_stats['total_operations']} "
                    f"(Success: {overall_stats['successful_operations']}, "
                    f"Failed: {overall_stats['failed_operations']})"
                )
                logger.info(f"Success Rate: {overall_stats['success_rate']:.1%}")
                logger.info(
                    f"Latency: {overall_stats['avg_latency_ms']:.2f}ms avg, "
                    f"{overall_stats['p95_latency_ms']:.2f}ms p95"
                )
                logger.info(f"Retries: {overall_stats['total_retries']} total")

                # Per-operation breakdown
                for op_type in ["freebusy_query", "create_event", "update_event", "delete_event"]:
                    stats = tracker.get_stats(op_type)
                    if stats["total_operations"] > 0:
                        logger.info(
                            f"  {op_type}: {stats['total_operations']} ops, "
                            f"{stats['success_rate']:.1%} success, "
                            f"{stats['avg_latency_ms']:.0f}ms avg"
                        )

                # Check health
                health = tracker.check_health()
                if health["status"] != "healthy":
                    logger.warning(f"⚠️  Calendar service is {health['status']}")
                    for alert in health["alerts"]:
                        logger.warning(f"  - {alert}")
            else:
                logger.info("No calendar operations recorded yet")

            logger.info("=" * 60)

        except asyncio.CancelledError:
            logger.info("Calendar metrics logging task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in periodic calendar metrics logging: {e}", exc_info=True)
            # Continue running despite errors


async def startup_background_tasks():
    """
    Start all background tasks.

    Add this to FastAPI app startup:
        @app.on_event("startup")
        async def startup():
            asyncio.create_task(startup_background_tasks())
    """
    logger.info("Starting background tasks...")

    # Start calendar metrics logging (every hour)
    asyncio.create_task(log_calendar_metrics_periodically(interval_seconds=3600))

    logger.info("Background tasks started")
