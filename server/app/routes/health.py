"""Health check endpoints."""

from app.services.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "ai-automotive-scheduler"}


@router.get("/health/db")
async def db_health_check(db: AsyncSession = Depends(get_db)):
    """Database health check."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@router.get("/health/redis")
async def redis_health_check():
    """Redis health check."""
    from app.services.redis_client import check_redis_health
    from fastapi import status
    from fastapi.responses import JSONResponse

    try:
        is_healthy = await check_redis_health()
        if is_healthy:
            return {"status": "healthy", "redis": "connected"}
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "redis": "disconnected"},
            )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "redis": "disconnected", "error": str(e)},
        )


@router.get("/health/calendar")
async def calendar_health_check():
    """
    Calendar service health check.

    Returns calendar operation metrics and health status.
    Useful for monitoring calendar integration reliability.
    """
    from app.utils.calendar_metrics import get_metrics_tracker
    from fastapi import status
    from fastapi.responses import JSONResponse

    try:
        tracker = get_metrics_tracker()
        health = tracker.check_health()

        # Return 503 if unhealthy, 200 otherwise
        if health["status"] == "unhealthy":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": health["status"],
                    "service": "calendar",
                    "alerts": health["alerts"],
                    "stats": health["stats"],
                },
            )

        return {
            "status": health["status"],
            "service": "calendar",
            "alerts": health["alerts"],
            "stats": health["stats"],
        }

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unknown",
                "service": "calendar",
                "error": str(e),
            },
        )
