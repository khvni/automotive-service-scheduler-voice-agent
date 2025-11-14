#!/usr/bin/env python3
"""
Test script for CRM tools (Feature 6).

Tests all 7 CRM tool functions with mock data and measures performance.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from app.models.appointment import Appointment, AppointmentStatus, ServiceType
from app.models.base import Base
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.services.redis_client import close_redis, init_redis
from app.tools.crm_tools import (
    book_appointment,
    cancel_appointment,
    decode_vin,
    get_available_slots,
    get_upcoming_appointments,
    lookup_customer,
    reschedule_appointment,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestResults:
    """Track test results and performance metrics."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def add_test(self, name: str, passed: bool, duration_ms: float, details: str = ""):
        self.tests.append(
            {"name": name, "passed": passed, "duration_ms": duration_ms, "details": details}
        )
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def print_summary(self):
        print("\n" + "=" * 70)
        print(f"TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed / (self.passed + self.failed) * 100):.1f}%")
        print("=" * 70)

        print("\nDETAILED RESULTS:")
        for test in self.tests:
            status = "PASS" if test["passed"] else "FAIL"
            print(f"  [{status}] {test['name']} ({test['duration_ms']:.2f}ms)")
            if test["details"]:
                print(f"        {test['details']}")


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

        print(f"Test database created with:")
        print(f"  - {2} customers")
        print(f"  - {2} vehicles")
        print(f"  - {1} appointment")
        print(f"  - Customer 1 ID: {customer1.id}, Phone: {customer1.phone_number}")
        print(f"  - Customer 2 ID: {customer2.id}, Phone: {customer2.phone_number}")
        print(f"  - Vehicle 1 ID: {vehicle1.id}, VIN: {vehicle1.vin}")
        print(f"  - Vehicle 2 ID: {vehicle2.id}, VIN: {vehicle2.vin}")
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


async def test_lookup_customer(session: AsyncSession, test_data: dict, results: TestResults):
    """Test Tool 1: lookup_customer"""
    print("\n--- Test 1: lookup_customer ---")

    # Test 1a: Found customer
    start = time.perf_counter()
    result = await lookup_customer(session, test_data["customer1_phone"])
    duration = (time.perf_counter() - start) * 1000

    success = (
        result is not None
        and result.get("id") == test_data["customer1_id"]
        and result.get("first_name") == "John"
        and len(result.get("vehicles", [])) == 1
    )
    results.add_test(
        "lookup_customer (found)", success, duration, f"Target: <30ms, Actual: {duration:.2f}ms"
    )
    print(f"  Found customer: {result.get('first_name')} {result.get('last_name')}")
    print(f"  Vehicles: {len(result.get('vehicles', []))}")
    print(f"  Duration: {duration:.2f}ms {'✓' if duration < 30 else '✗ (>30ms)'}")

    # Test 1b: Not found customer
    start = time.perf_counter()
    result = await lookup_customer(session, "+15559999999")
    duration = (time.perf_counter() - start) * 1000

    success = result is None
    results.add_test("lookup_customer (not found)", success, duration)
    print(f"  Not found test: {result is None} ({duration:.2f}ms)")


async def test_get_available_slots(results: TestResults):
    """Test Tool 2: get_available_slots"""
    print("\n--- Test 2: get_available_slots ---")

    # Test 2a: Weekday slots
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    if tomorrow.weekday() == 6:  # Skip if Sunday
        tomorrow = tomorrow + timedelta(days=1)

    start = time.perf_counter()
    result = await get_available_slots(tomorrow.isoformat(), duration_minutes=30)
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is True and len(result.get("available_slots", [])) > 0
    results.add_test("get_available_slots (weekday)", success, duration)
    print(f"  Date: {tomorrow} ({result.get('day_of_week')})")
    print(f"  Slots: {len(result.get('available_slots', []))}")
    print(f"  Duration: {duration:.2f}ms")

    # Test 2b: Sunday (closed)
    # Find next Sunday
    days_ahead = 6 - datetime.now().weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_sunday = (datetime.now() + timedelta(days=days_ahead)).date()

    start = time.perf_counter()
    result = await get_available_slots(next_sunday.isoformat())
    duration = (time.perf_counter() - start) * 1000

    success = (
        result.get("success") is True
        and len(result.get("available_slots", [])) == 0
        and "closed on Sundays" in result.get("message", "").lower()
    )
    results.add_test("get_available_slots (Sunday closed)", success, duration)
    print(f"  Sunday test: {len(result.get('available_slots', []))} slots (expected 0)")


async def test_book_appointment(session: AsyncSession, test_data: dict, results: TestResults):
    """Test Tool 3: book_appointment"""
    print("\n--- Test 3: book_appointment ---")

    # Test 3a: Valid booking
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
        result.get("success") is True and result.get("data", {}).get("appointment_id") is not None
    )
    results.add_test(
        "book_appointment (valid)", success, duration, f"Target: <100ms, Actual: {duration:.2f}ms"
    )
    print(f"  Booked: {result.get('success')}")
    print(f"  Appointment ID: {result.get('data', {}).get('appointment_id')}")
    print(f"  Duration: {duration:.2f}ms {'✓' if duration < 100 else '✗ (>100ms)'}")

    # Save appointment ID for later tests
    if success:
        test_data["new_appointment_id"] = result.get("data", {}).get("appointment_id")

    # Test 3b: Invalid customer
    start = time.perf_counter()
    result = await book_appointment(
        db=session,
        customer_id=99999,
        vehicle_id=test_data["vehicle1_id"],
        scheduled_at=future_time.isoformat(),
        service_type="oil_change",
    )
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is False and "not found" in result.get("message", "").lower()
    results.add_test("book_appointment (invalid customer)", success, duration)
    print(f"  Invalid customer test: {result.get('success') is False}")


async def test_get_upcoming_appointments(
    session: AsyncSession, test_data: dict, results: TestResults
):
    """Test Tool 4: get_upcoming_appointments"""
    print("\n--- Test 4: get_upcoming_appointments ---")

    # Test 4a: Customer with appointments
    start = time.perf_counter()
    result = await get_upcoming_appointments(session, test_data["customer1_id"])
    duration = (time.perf_counter() - start) * 1000

    appointments = result.get("data", {}).get("appointments", [])
    success = result.get("success") is True and len(appointments) >= 1
    results.add_test("get_upcoming_appointments (with appointments)", success, duration)
    print(f"  Customer 1 appointments: {len(appointments)}")
    print(f"  Duration: {duration:.2f}ms")

    # Test 4b: Customer with no appointments (or invalid)
    start = time.perf_counter()
    result = await get_upcoming_appointments(session, 99999)
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is False
    results.add_test("get_upcoming_appointments (invalid customer)", success, duration)
    print(f"  Invalid customer test: {result.get('success') is False}")


async def test_reschedule_appointment(session: AsyncSession, test_data: dict, results: TestResults):
    """Test Tool 6: reschedule_appointment"""
    print("\n--- Test 5: reschedule_appointment ---")

    # Test 5a: Valid reschedule
    new_time = (datetime.now(timezone.utc) + timedelta(days=10)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )

    start = time.perf_counter()
    result = await reschedule_appointment(
        db=session, appointment_id=test_data["appointment1_id"], new_datetime=new_time.isoformat()
    )
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is True
    results.add_test("reschedule_appointment (valid)", success, duration)
    print(f"  Rescheduled: {result.get('success')}")
    print(f"  New time: {result.get('data', {}).get('new_datetime')}")
    print(f"  Duration: {duration:.2f}ms")

    # Test 5b: Invalid appointment
    start = time.perf_counter()
    result = await reschedule_appointment(
        db=session, appointment_id=99999, new_datetime=new_time.isoformat()
    )
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is False
    results.add_test("reschedule_appointment (invalid)", success, duration)
    print(f"  Invalid appointment test: {result.get('success') is False}")


async def test_cancel_appointment(session: AsyncSession, test_data: dict, results: TestResults):
    """Test Tool 5: cancel_appointment"""
    print("\n--- Test 6: cancel_appointment ---")

    # Use the newly booked appointment
    appointment_id = test_data.get("new_appointment_id", test_data["appointment1_id"])

    # Test 6a: Valid cancellation
    start = time.perf_counter()
    result = await cancel_appointment(
        db=session, appointment_id=appointment_id, reason="Schedule conflict"
    )
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is True
    results.add_test("cancel_appointment (valid)", success, duration)
    print(f"  Cancelled: {result.get('success')}")
    print(f"  Reason: {result.get('data', {}).get('cancellation_reason')}")
    print(f"  Duration: {duration:.2f}ms")

    # Test 6b: Already cancelled
    start = time.perf_counter()
    result = await cancel_appointment(db=session, appointment_id=appointment_id, reason="Test")
    duration = (time.perf_counter() - start) * 1000

    success = (
        result.get("success") is False and "already cancelled" in result.get("error", "").lower()
    )
    results.add_test("cancel_appointment (already cancelled)", success, duration)
    print(f"  Already cancelled test: {result.get('success') is False}")


async def test_decode_vin(results: TestResults):
    """Test Tool 7: decode_vin"""
    print("\n--- Test 7: decode_vin ---")

    # Test 7a: Valid VIN
    valid_vin = "1HGCM82633A123456"

    start = time.perf_counter()
    result = await decode_vin(valid_vin)
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is True
    results.add_test(
        "decode_vin (valid)", success, duration, f"Target: <500ms, Actual: {duration:.2f}ms"
    )
    print(f"  VIN: {valid_vin}")
    print(f"  Decoded: {result.get('success')}")
    if result.get("success"):
        data = result.get("data", {})
        print(f"  Vehicle: {data.get('year')} {data.get('make')} {data.get('model')}")
    print(f"  Duration: {duration:.2f}ms {'✓' if duration < 500 else '✗ (>500ms)'}")

    # Test 7b: Invalid VIN (too short)
    start = time.perf_counter()
    result = await decode_vin("TOOSHORT")
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is False
    results.add_test("decode_vin (invalid length)", success, duration)
    print(f"  Invalid VIN test: {result.get('success') is False}")

    # Test 7c: Invalid characters
    start = time.perf_counter()
    result = await decode_vin("1HGCM82633A12345O")  # Contains 'O'
    duration = (time.perf_counter() - start) * 1000

    success = result.get("success") is False
    results.add_test("decode_vin (invalid characters)", success, duration)
    print(f"  Invalid characters test: {result.get('success') is False}")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("CRM TOOLS TEST SUITE (Feature 6)")
    print("=" * 70)

    results = TestResults()

    try:
        # Setup test database
        print("\nSetting up test database...")
        engine, session_maker, test_data = await setup_test_database()

        # Initialize Redis (optional for tests)
        try:
            await init_redis()
            print("Redis initialized for caching tests")
        except Exception as e:
            print(f"Redis not available (caching tests will be skipped): {e}")

        # Run tests
        async with session_maker() as session:
            await test_lookup_customer(session, test_data, results)
            await test_get_available_slots(results)
            await test_book_appointment(session, test_data, results)
            await test_get_upcoming_appointments(session, test_data, results)
            await test_reschedule_appointment(session, test_data, results)
            await test_cancel_appointment(session, test_data, results)

        # Decode VIN test (no database needed)
        await test_decode_vin(results)

        # Print summary
        results.print_summary()

        # Cleanup
        await engine.dispose()
        try:
            await close_redis()
        except:
            pass

        # Exit code based on results
        return 0 if results.failed == 0 else 1

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
