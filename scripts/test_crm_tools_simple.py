#!/usr/bin/env python3
"""
Simple test script for CRM tools (Feature 6).
Tests functionality without requiring Redis or full app initialization.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

# Set up minimal environment
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DEEPGRAM_API_KEY", "test")

# Import only the functions we need directly
import sys

from app.models.appointment import Appointment, AppointmentStatus, ServiceType
from app.models.base import Base
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(project_root / "server" / "app" / "tools"))


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)


def print_test(name, passed, duration_ms, details=""):
    """Print test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  [{status}] {name} ({duration_ms:.2f}ms)")
    if details:
        print(f"        {details}")


async def setup_test_database():
    """Create test database with schema and mock data."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session maker
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    # Populate with test data
    async with async_session_maker() as session:
        # Create test customers
        customer1 = Customer(
            phone_number="+15555551234",
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            customer_since=datetime.now(timezone.utc).date() - timedelta(days=365),
        )
        customer2 = Customer(
            phone_number="+15555555678",
            email="jane.smith@example.com",
            first_name="Jane",
            last_name="Smith",
            customer_since=datetime.now(timezone.utc).date() - timedelta(days=180),
        )

        session.add_all([customer1, customer2])
        await session.commit()
        await session.refresh(customer1)
        await session.refresh(customer2)

        # Create test vehicles
        vehicle1 = Vehicle(
            customer_id=customer1.id,
            vin="1HGCM82633A123456",
            year=2020,
            make="Honda",
            model="Accord",
            trim="EX",
            color="Silver",
            current_mileage=45000,
            is_primary_vehicle=True,
        )
        vehicle2 = Vehicle(
            customer_id=customer2.id,
            vin="5FNRL6H75NB012345",
            year=2022,
            make="Honda",
            model="Odyssey",
            trim="Touring",
            color="White",
            current_mileage=12000,
            is_primary_vehicle=True,
        )

        session.add_all([vehicle1, vehicle2])
        await session.commit()
        await session.refresh(vehicle1)
        await session.refresh(vehicle2)

        # Create test appointments
        future_date = datetime.now(timezone.utc) + timedelta(days=7)
        appointment1 = Appointment(
            customer_id=customer1.id,
            vehicle_id=vehicle1.id,
            scheduled_at=future_date,
            duration_minutes=60,
            service_type=ServiceType.OIL_CHANGE,
            status=AppointmentStatus.SCHEDULED,
            booking_method="phone",
        )

        session.add(appointment1)
        await session.commit()
        await session.refresh(appointment1)

        print(f"\nTest database created:")
        print(f"  - Customer 1 ID: {customer1.id}, Phone: {customer1.phone_number}")
        print(f"  - Customer 2 ID: {customer2.id}, Phone: {customer2.phone_number}")
        print(f"  - Vehicle 1 ID: {vehicle1.id}")
        print(f"  - Vehicle 2 ID: {vehicle2.id}")
        print(f"  - Appointment 1 ID: {appointment1.id}")

        return (
            engine,
            async_session_maker,
            {
                "customer1_id": customer1.id,
                "customer1_phone": customer1.phone_number,
                "customer2_id": customer2.id,
                "customer2_phone": customer2.phone_number,
                "vehicle1_id": vehicle1.id,
                "vehicle2_id": vehicle2.id,
                "appointment1_id": appointment1.id,
            },
        )


async def main():
    """Run all tests."""
    print_header("CRM TOOLS TEST SUITE (Feature 6)")

    passed = 0
    failed = 0

    try:
        # Setup test database
        print("\nSetting up test database...")
        engine, session_maker, test_data = await setup_test_database()

        # Import tools dynamically to avoid circular import issues
        from crm_tools import (
            book_appointment,
            cancel_appointment,
            decode_vin,
            get_available_slots,
            get_upcoming_appointments,
            lookup_customer,
            reschedule_appointment,
        )

        print_header("Running Tests")

        # Test 1: lookup_customer
        print("\n1. Testing lookup_customer...")
        async with session_maker() as session:
            start = time.perf_counter()
            result = await lookup_customer(session, test_data["customer1_phone"])
            duration = (time.perf_counter() - start) * 1000

            success = (
                result is not None
                and result.get("id") == test_data["customer1_id"]
                and len(result.get("vehicles", [])) == 1
            )
            if success:
                passed += 1
                print(f"  Customer found: {result.get('first_name')} {result.get('last_name')}")
            else:
                failed += 1
            print_test(
                "lookup_customer (found)",
                success,
                duration,
                f"Target: <30ms, Actual: {duration:.2f}ms",
            )

        # Test 2: get_available_slots
        print("\n2. Testing get_available_slots...")
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        if tomorrow.weekday() == 6:
            tomorrow = tomorrow + timedelta(days=1)

        start = time.perf_counter()
        result = await get_available_slots(tomorrow.isoformat(), duration_minutes=30)
        duration = (time.perf_counter() - start) * 1000

        success = result.get("success") is True and len(result.get("available_slots", [])) > 0
        if success:
            passed += 1
            print(f"  Found {len(result.get('available_slots', []))} slots for {tomorrow}")
        else:
            failed += 1
        print_test("get_available_slots", success, duration)

        # Test 3: book_appointment
        print("\n3. Testing book_appointment...")
        async with session_maker() as session:
            future_time = (datetime.now(timezone.utc) + timedelta(days=3)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )

            start = time.perf_counter()
            result = await book_appointment(
                db=session,
                customer_id=test_data["customer2_id"],
                vehicle_id=test_data["vehicle2_id"],
                scheduled_at=future_time.isoformat(),
                service_type="oil_change",
                duration_minutes=30,
                customer_concerns="Strange noise from engine",
            )
            duration = (time.perf_counter() - start) * 1000

            success = (
                result.get("success") is True
                and result.get("data", {}).get("appointment_id") is not None
            )
            if success:
                passed += 1
                print(f"  Appointment booked: ID {result.get('data', {}).get('appointment_id')}")
                test_data["new_appointment_id"] = result.get("data", {}).get("appointment_id")
            else:
                failed += 1
            print_test(
                "book_appointment", success, duration, f"Target: <100ms, Actual: {duration:.2f}ms"
            )

        # Test 4: get_upcoming_appointments
        print("\n4. Testing get_upcoming_appointments...")
        async with session_maker() as session:
            start = time.perf_counter()
            result = await get_upcoming_appointments(session, test_data["customer1_id"])
            duration = (time.perf_counter() - start) * 1000

            appointments = result.get("data", {}).get("appointments", [])
            success = result.get("success") is True and len(appointments) >= 1
            if success:
                passed += 1
                print(f"  Found {len(appointments)} upcoming appointments")
            else:
                failed += 1
            print_test("get_upcoming_appointments", success, duration)

        # Test 5: reschedule_appointment
        print("\n5. Testing reschedule_appointment...")
        async with session_maker() as session:
            new_time = (datetime.now(timezone.utc) + timedelta(days=10)).replace(
                hour=14, minute=0, second=0, microsecond=0
            )

            start = time.perf_counter()
            result = await reschedule_appointment(
                db=session,
                appointment_id=test_data["appointment1_id"],
                new_datetime=new_time.isoformat(),
            )
            duration = (time.perf_counter() - start) * 1000

            success = result.get("success") is True
            if success:
                passed += 1
                print(f"  Rescheduled to {new_time.strftime('%Y-%m-%d %H:%M')}")
            else:
                failed += 1
            print_test("reschedule_appointment", success, duration)

        # Test 6: cancel_appointment
        print("\n6. Testing cancel_appointment...")
        async with session_maker() as session:
            appointment_id = test_data.get("new_appointment_id", test_data["appointment1_id"])

            start = time.perf_counter()
            result = await cancel_appointment(
                db=session, appointment_id=appointment_id, reason="Schedule conflict"
            )
            duration = (time.perf_counter() - start) * 1000

            success = result.get("success") is True
            if success:
                passed += 1
                print(f"  Cancelled appointment {appointment_id}")
            else:
                failed += 1
            print_test("cancel_appointment", success, duration)

        # Test 7: decode_vin
        print("\n7. Testing decode_vin...")
        valid_vin = "1HGCM82633A123456"

        start = time.perf_counter()
        result = await decode_vin(valid_vin)
        duration = (time.perf_counter() - start) * 1000

        success = result.get("success") is True
        if success:
            passed += 1
            data = result.get("data", {})
            print(f"  Decoded: {data.get('year')} {data.get('make')} {data.get('model')}")
        else:
            failed += 1
        print_test("decode_vin", success, duration, f"Target: <500ms, Actual: {duration:.2f}ms")

        # Summary
        print_header("TEST SUMMARY")
        total = passed + failed
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed / total * 100):.1f}%")
        print("=" * 70)

        # Cleanup
        await engine.dispose()

        return 0 if failed == 0 else 1

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
