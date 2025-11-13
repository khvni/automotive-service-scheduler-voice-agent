"""Database connection and session management."""

from app.config import settings
from app.models.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = None
async_session_maker = None


async def init_db():
    """Initialize database engine and create tables."""
    global engine, async_session_maker

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=True,
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database engine."""
    global engine
    if engine:
        await engine.dispose()


async def get_db() -> AsyncSession:
    """Get database session."""
    async with async_session_maker() as session:
        yield session
