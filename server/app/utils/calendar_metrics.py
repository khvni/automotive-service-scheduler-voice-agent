"""
Calendar operation metrics tracking.

Tracks performance and reliability metrics for Google Calendar operations:
- API call latency (freebusy, create, update, delete)
- Success/failure rates
- Retry attempts
- Error types
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CalendarOperationMetrics:
    """Metrics for a single calendar operation."""

    operation: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    success: bool = False
    retry_count: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Get operation duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def mark_success(self) -> None:
        """Mark operation as successful."""
        self.end_time = time.time()
        self.success = True
        logger.info(
            f"✅ Calendar {self.operation} succeeded in {self.duration_ms:.2f}ms "
            f"(retries: {self.retry_count})"
        )

    def mark_failure(self, error: Exception) -> None:
        """Mark operation as failed."""
        self.end_time = time.time()
        self.success = False
        self.error_type = type(error).__name__
        self.error_message = str(error)
        logger.error(
            f"❌ Calendar {self.operation} failed after {self.duration_ms:.2f}ms "
            f"(retries: {self.retry_count}): {self.error_type}: {self.error_message}"
        )

    def increment_retry(self) -> None:
        """Increment retry counter."""
        self.retry_count += 1
        logger.warning(
            f"🔄 Calendar {self.operation} retry #{self.retry_count}"
        )


class CalendarMetricsTracker:
    """
    Track and aggregate calendar operation metrics.

    Provides insights into:
    - Average latencies per operation type
    - Success/failure rates
    - Common error types
    """

    def __init__(self):
        """Initialize metrics tracker."""
        self.operations: Dict[str, list[CalendarOperationMetrics]] = {
            "freebusy_query": [],
            "create_event": [],
            "update_event": [],
            "delete_event": [],
            "get_event": [],
        }
        self.total_operations = 0
        self.total_failures = 0

    def start_operation(self, operation: str) -> CalendarOperationMetrics:
        """
        Start tracking a calendar operation.

        Args:
            operation: Operation type (e.g., "freebusy_query")

        Returns:
            CalendarOperationMetrics instance to track the operation
        """
        metric = CalendarOperationMetrics(operation=operation)
        logger.debug(f"📊 Starting calendar operation: {operation}")
        return metric

    def record_operation(self, metric: CalendarOperationMetrics) -> None:
        """
        Record a completed operation.

        Args:
            metric: Completed operation metrics
        """
        if metric.operation in self.operations:
            self.operations[metric.operation].append(metric)

        self.total_operations += 1
        if not metric.success:
            self.total_failures += 1

        # Log warning if operation was slow
        if metric.duration_ms > 2000:  # More than 2 seconds
            logger.warning(
                f"⏱️  Slow calendar operation: {metric.operation} took {metric.duration_ms:.2f}ms"
            )

    def get_stats(self, operation: Optional[str] = None) -> Dict:
        """
        Get aggregated statistics.

        Args:
            operation: Specific operation type, or None for all operations

        Returns:
            Dictionary with statistics
        """
        if operation and operation in self.operations:
            ops = self.operations[operation]
        else:
            ops = [op for op_list in self.operations.values() for op in op_list]

        if not ops:
            return {
                "total_operations": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "total_retries": 0,
            }

        successful_ops = [op for op in ops if op.success]
        latencies = sorted([op.duration_ms for op in ops])
        total_retries = sum(op.retry_count for op in ops)

        # Calculate p95 latency (95th percentile)
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index] if latencies else 0.0

        return {
            "total_operations": len(ops),
            "successful_operations": len(successful_ops),
            "failed_operations": len(ops) - len(successful_ops),
            "success_rate": len(successful_ops) / len(ops) if ops else 0.0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "p95_latency_ms": p95_latency,
            "total_retries": total_retries,
        }

    def log_summary(self) -> None:
        """Log a summary of all calendar operation metrics."""
        logger.info("=" * 60)
        logger.info("📊 CALENDAR OPERATIONS METRICS SUMMARY")
        logger.info("=" * 60)

        overall_stats = self.get_stats()
        logger.info(
            f"Overall: {overall_stats['total_operations']} operations, "
            f"{overall_stats['success_rate']:.1%} success rate"
        )
        logger.info(
            f"Latency: {overall_stats['avg_latency_ms']:.2f}ms avg, "
            f"{overall_stats['p95_latency_ms']:.2f}ms p95"
        )
        logger.info(f"Retries: {overall_stats['total_retries']} total")

        # Per-operation breakdown
        for op_type in self.operations.keys():
            stats = self.get_stats(op_type)
            if stats["total_operations"] > 0:
                logger.info(
                    f"  {op_type}: {stats['total_operations']} ops, "
                    f"{stats['success_rate']:.1%} success, "
                    f"{stats['avg_latency_ms']:.0f}ms avg"
                )

        logger.info("=" * 60)

    def check_health(self) -> Dict:
        """
        Check calendar service health based on metrics.

        Returns:
            Dictionary with health status and alerts
        """
        stats = self.get_stats()
        alerts = []
        status = "healthy"

        # Check success rate
        if stats["success_rate"] < 0.95 and stats["total_operations"] >= 10:
            alerts.append(f"Low success rate: {stats['success_rate']:.1%}")
            status = "degraded"

        # Check latency
        if stats["avg_latency_ms"] > 2000:
            alerts.append(f"High average latency: {stats['avg_latency_ms']:.0f}ms")
            status = "degraded"

        # Check retry rate
        if stats["total_operations"] > 0:
            retry_rate = stats["total_retries"] / stats["total_operations"]
            if retry_rate > 0.5:  # More than 50% operations needed retries
                alerts.append(f"High retry rate: {retry_rate:.1%}")
                status = "degraded"

        if stats["failed_operations"] > 10:
            status = "unhealthy"
            alerts.append(f"Many failures: {stats['failed_operations']}")

        return {
            "status": status,
            "alerts": alerts,
            "stats": stats,
        }


# Global metrics tracker instance
_metrics_tracker: Optional[CalendarMetricsTracker] = None


def get_metrics_tracker() -> CalendarMetricsTracker:
    """Get the global calendar metrics tracker instance."""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = CalendarMetricsTracker()
    return _metrics_tracker
