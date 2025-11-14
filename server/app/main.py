"""
Main FastAPI application for AI Automotive Service Scheduler.
Handles WebSocket connections for voice streaming and tool orchestration.
"""

from contextlib import asynccontextmanager

from app.config import settings
from app.routes import health, voice, webhooks
from app.services.database import close_db, init_db
from app.services.redis_client import close_redis, init_redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown tasks."""
    # Startup
    await init_db()
    await init_redis()

    # Start background tasks for monitoring
    import asyncio

    from app.utils.background_tasks import startup_background_tasks

    asyncio.create_task(startup_background_tasks())

    yield
    # Shutdown
    await close_db()
    await close_redis()


app = FastAPI(
    title="AI Automotive Service Scheduler",
    description="Real-time voice agent for automotive service scheduling",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(voice.router, prefix="/api/v1/voice", tags=["voice"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "AI Automotive Service Scheduler",
        "version": "1.0.0",
        "status": "running",
    }
