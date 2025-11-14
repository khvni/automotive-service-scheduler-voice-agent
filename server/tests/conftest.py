"""Pytest configuration and fixtures."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Test database URL
TEST_DATABASE_URL = settings.DATABASE_URL.replace("automotive_voice", "automotive_voice_test")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_customer(db_session: AsyncSession) -> Customer:
    """Create test customer."""
    customer = Customer(
        name="John Doe",
        phone_number="+15555551234",
        email="john.doe@example.com",
        date_of_birth=datetime(1980, 5, 15).date(),
        street_address="123 Main St",
        city="Springfield",
        state="IL",
        zip_code="62701",
        preferred_contact_method="phone",
        communication_preferences={"sms_reminders": True, "email_updates": True},
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


@pytest_asyncio.fixture
async def test_vehicle(db_session: AsyncSession, test_customer: Customer) -> Vehicle:
    """Create test vehicle."""
    vehicle = Vehicle(
        customer_id=test_customer.id,
        vin="1HGBH41JXMN109186",
        year=2021,
        make="Honda",
        model="Accord",
        trim="EX-L",
        mileage=25000,
        license_plate="ABC123",
        color="Silver",
    )
    db_session.add(vehicle)
    await db_session.commit()
    await db_session.refresh(vehicle)
    return vehicle


@pytest_asyncio.fixture
async def test_appointment(
    db_session: AsyncSession, test_customer: Customer, test_vehicle: Vehicle
) -> Appointment:
    """Create test appointment."""
    appointment_time = datetime.now(timezone.utc) + timedelta(days=7)
    appointment = Appointment(
        customer_id=test_customer.id,
        vehicle_id=test_vehicle.id,
        scheduled_time=appointment_time,
        service_type="Oil Change",
        status="scheduled",
        duration_minutes=30,
        notes="Regular maintenance",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment
