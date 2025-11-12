#!/usr/bin/env python3
"""
Initialize database with sample data for development/testing.
"""

import asyncio
import sys
from pathlib import Path

# Add server directory to path
sys.path.append(str(Path(__file__).parent.parent / "server"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timedelta

from app.config import settings
from app.models import Customer, Vehicle, Appointment
from app.models.appointment import AppointmentStatus, ServiceType
from app.models.base import Base


async def init_database():
    """Create tables and seed with sample data."""
    print("Initializing database...")

    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Create tables
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed sample data
    print("Seeding sample data...")
    async with async_session_maker() as db:
        # Create sample customers
        customers = [
            Customer(
                phone_number="+15551234567",
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
                last_service_date=datetime.now() - timedelta(days=90),
            ),
            Customer(
                phone_number="+15559876543",
                first_name="Jane",
                last_name="Smith",
                email="jane.smith@example.com",
                last_service_date=datetime.now() - timedelta(days=45),
            ),
            Customer(
                phone_number="+15555555555",
                first_name="Bob",
                last_name="Johnson",
                email="bob.johnson@example.com",
            ),
        ]

        for customer in customers:
            db.add(customer)

        await db.commit()

        # Refresh to get IDs
        for customer in customers:
            await db.refresh(customer)

        # Create sample vehicles
        vehicles = [
            Vehicle(
                customer_id=customers[0].id,
                vin="1HGBH41JXMN109186",
                make="Honda",
                model="Accord",
                year=2021,
                color="Silver",
                mileage=35000,
            ),
            Vehicle(
                customer_id=customers[1].id,
                vin="1FTFW1ET5DFC10314",
                make="Ford",
                model="F-150",
                year=2020,
                color="Blue",
                mileage=52000,
            ),
            Vehicle(
                customer_id=customers[2].id,
                vin="5FNRL6H77JB002378",
                make="Toyota",
                model="Camry",
                year=2022,
                color="White",
                mileage=12000,
            ),
        ]

        for vehicle in vehicles:
            db.add(vehicle)

        await db.commit()

        # Refresh to get IDs
        for vehicle in vehicles:
            await db.refresh(vehicle)

        # Create sample appointments
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

        appointments = [
            Appointment(
                customer_id=customers[0].id,
                vehicle_id=vehicles[0].id,
                scheduled_at=tomorrow,
                service_type=ServiceType.OIL_CHANGE,
                status=AppointmentStatus.CONFIRMED,
                service_description="Regular oil change and filter replacement",
                estimated_cost=5000,  # $50.00
            ),
            Appointment(
                customer_id=customers[1].id,
                vehicle_id=vehicles[1].id,
                scheduled_at=tomorrow + timedelta(hours=2),
                service_type=ServiceType.TIRE_ROTATION,
                status=AppointmentStatus.PENDING,
                service_description="Tire rotation and pressure check",
                estimated_cost=4000,  # $40.00
            ),
        ]

        for appointment in appointments:
            db.add(appointment)

        await db.commit()

    print("Database initialized successfully!")
    print(f"Created {len(customers)} customers")
    print(f"Created {len(vehicles)} vehicles")
    print(f"Created {len(appointments)} appointments")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())
