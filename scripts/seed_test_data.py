#!/usr/bin/env python3
"""
Seed Test Data for Voice Agent Development

This script populates the database with realistic test data for developing
and testing the voice agent:
- Sample customers with phone numbers
- Vehicles (including the classic 2001 Honda Odyssey)
- Upcoming appointments for outbound call testing
- Service history

Usage:
    python scripts/seed_test_data.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from app.config import settings
from app.models.appointment import Appointment, AppointmentStatus, ServiceType
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.services.database import get_db
from sqlalchemy import select


async def seed_data():
    """Seed the database with test data."""
    print("🌱 Seeding test data...")

    # Suppress SQLAlchemy logging during seed to reduce noise
    import logging
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

    # Initialize database
    from app.services.database import init_db
    await init_db()

    # Get database session
    db_gen = get_db()
    db = await db_gen.__anext__()

    try:
        # Check if data already exists
        result = await db.execute(select(Customer).where(Customer.first_name == "Ali"))
        existing = result.scalar_one_or_none()

        if existing:
            print("⚠️  Test data already exists. Skipping seed.")
            print("   To re-seed, delete existing test customers first.")
            return

        print("\n📋 Creating test customers...")

        # Customer 1: Ali Khani (2019 Honda CR-V owner)
        customer1 = Customer(
            phone_number="+14086137788",  # Ali's test number
            email="byalikhani@gmail.com",
            first_name="Ali",
            last_name="Khani",
            street_address="123 Main Street",
            city="San Jose",
            state="CA",
            zip_code="95110",
            customer_since=datetime.now().date() - timedelta(days=730),  # Customer for 2 years
            customer_type="retail",
            preferred_contact_method="phone",
            receive_reminders=True,
            preferred_appointment_time="morning",
        )
        db.add(customer1)
        await db.flush()  # Get customer1.id

        # Ali's vehicles
        vehicle1 = Vehicle(
            customer_id=customer1.id,
            vin="2HKRM4H77KH123456",
            license_plate="ABC1234",
            year=2019,
            make="Honda",
            model="CR-V",
            trim="EX",
            color="Silver",
            current_mileage=45000,
            last_service_date=(datetime.now() - timedelta(days=45)).date(),
            last_service_mileage=44000,
            is_primary_vehicle=True,
        )
        db.add(vehicle1)
        await db.flush()

        # Upcoming oil change appointment for Ali
        appointment1 = Appointment(
            customer_id=customer1.id,
            vehicle_id=vehicle1.id,
            scheduled_at=datetime.now() + timedelta(days=3, hours=10),  # 3 days from now at 10 AM
            duration_minutes=45,
            service_type=ServiceType.OIL_CHANGE,
            service_description="Oil change and filter replacement",
            estimated_cost=Decimal("65.00"),
            status=AppointmentStatus.SCHEDULED,
            booking_method="phone",
            booked_by="Sarah (receptionist)",
        )
        db.add(appointment1)

        print(f"✓ Created customer: {customer1.first_name} {customer1.last_name} ({customer1.phone_number})")
        print(f"  - Vehicle: {vehicle1.year} {vehicle1.make} {vehicle1.model}")
        print(f"  - Appointment: {appointment1.service_type.value} on {appointment1.scheduled_at}")

        # Customer 2: Maria Garcia
        customer2 = Customer(
            phone_number="+15125551001",
            email="maria.garcia@example.com",
            first_name="Maria",
            last_name="Garcia",
            street_address="456 Oak Avenue",
            city="Austin",
            state="TX",
            zip_code="78702",
            customer_since=datetime.now().date() - timedelta(days=365),
            customer_type="retail",
            preferred_contact_method="phone",
            receive_reminders=True,
        )
        db.add(customer2)
        await db.flush()

        vehicle2 = Vehicle(
            customer_id=customer2.id,
            vin="1HGCM82633A123456",
            license_plate="XYZ5678",
            year=2018,
            make="Toyota",
            model="Camry",
            trim="SE",
            color="Blue",
            current_mileage=45000,
            is_primary_vehicle=True,
        )
        db.add(vehicle2)
        await db.flush()

        appointment2 = Appointment(
            customer_id=customer2.id,
            vehicle_id=vehicle2.id,
            scheduled_at=datetime.now() + timedelta(days=1, hours=14),  # Tomorrow at 2 PM
            duration_minutes=90,
            service_type=ServiceType.BRAKE_SERVICE,
            service_description="Brake pad replacement and rotor inspection",
            estimated_cost=Decimal("350.00"),
            status=AppointmentStatus.SCHEDULED,
            booking_method="online",
        )
        db.add(appointment2)

        print(f"✓ Created customer: {customer2.first_name} {customer2.last_name}")
        print(f"  - Vehicle: {vehicle2.year} {vehicle2.make} {vehicle2.model}")
        print(f"  - Appointment: {appointment2.service_type.value} on {appointment2.scheduled_at}")

        # Customer 3: Robert Johnson (multiple vehicles)
        customer3 = Customer(
            phone_number="+15125551002",
            email="robert.johnson@example.com",
            first_name="Robert",
            last_name="Johnson",
            street_address="789 Elm Street",
            city="Austin",
            state="TX",
            zip_code="78703",
            customer_since=datetime.now().date() - timedelta(days=1095),  # 3 years
            customer_type="retail",
            preferred_contact_method="phone",
        )
        db.add(customer3)
        await db.flush()

        vehicle3a = Vehicle(
            customer_id=customer3.id,
            vin="5FNRL5H40GB123456",
            license_plate="DEF9012",
            year=2016,
            make="Honda",
            model="CR-V",
            trim="EX-L",
            color="White",
            current_mileage=62000,
            is_primary_vehicle=True,
        )
        db.add(vehicle3a)

        vehicle3b = Vehicle(
            customer_id=customer3.id,
            vin="1FTFW1ET5BFC12345",
            license_plate="GHI3456",
            year=2011,
            make="Ford",
            model="F-150",
            trim="XLT",
            color="Black",
            current_mileage=98000,
            is_primary_vehicle=False,
        )
        db.add(vehicle3b)

        print(f"✓ Created customer: {customer3.first_name} {customer3.last_name}")
        print(f"  - Vehicle 1: {vehicle3a.year} {vehicle3a.make} {vehicle3a.model}")
        print(f"  - Vehicle 2: {vehicle3b.year} {vehicle3b.make} {vehicle3b.model}")

        # Customer 4: Lisa Chen (recent customer)
        customer4 = Customer(
            phone_number="+15125551003",
            email="lisa.chen@example.com",
            first_name="Lisa",
            last_name="Chen",
            street_address="321 Pine Road",
            city="Austin",
            state="TX",
            zip_code="78704",
            customer_since=datetime.now().date() - timedelta(days=90),
            customer_type="retail",
            preferred_contact_method="phone",
        )
        db.add(customer4)
        await db.flush()

        vehicle4 = Vehicle(
            customer_id=customer4.id,
            vin="3VW2B7AJ5HM123456",
            license_plate="JKL7890",
            year=2020,
            make="Volkswagen",
            model="Jetta",
            trim="SEL",
            color="Gray",
            current_mileage=15000,
            is_primary_vehicle=True,
        )
        db.add(vehicle4)
        await db.flush()

        appointment4 = Appointment(
            customer_id=customer4.id,
            vehicle_id=vehicle4.id,
            scheduled_at=datetime.now() + timedelta(days=7, hours=9),  # Next week at 9 AM
            duration_minutes=120,
            service_type=ServiceType.INSPECTION,
            service_description="State inspection",
            estimated_cost=Decimal("25.00"),
            status=AppointmentStatus.SCHEDULED,
            booking_method="ai_voice",
            booked_by="AI Voice Agent",
        )
        db.add(appointment4)

        print(f"✓ Created customer: {customer4.first_name} {customer4.last_name}")
        print(f"  - Vehicle: {vehicle4.year} {vehicle4.make} {vehicle4.model}")
        print(f"  - Appointment: {appointment4.service_type.value} on {appointment4.scheduled_at}")

        # Commit all changes
        await db.commit()

        print("\n✅ Test data seeded successfully!")
        print(f"\n📊 Summary:")
        print(f"   - 4 customers created")
        print(f"   - 5 vehicles created")
        print(f"   - 3 upcoming appointments created")
        print(f"\n💡 Test by calling:")
        print(f"   - Your number (+14086137788) for Ali Khani's 2019 Honda CR-V")
        print(f"   - Run outbound test to get appointment reminder call")

    except Exception as e:
        await db.rollback()
        print(f"\n❌ Error seeding data: {e}")
        raise
    finally:
        await db.close()


def main():
    """Main entry point."""
    asyncio.run(seed_data())


if __name__ == "__main__":
    main()
