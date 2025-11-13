#!/usr/bin/env python3
"""
Test script for appointment reminder job.

This script:
1. Creates a test appointment for tomorrow
2. Runs the reminder job manually
3. Verifies that the Twilio call was initiated
4. Checks the call log in the database

Usage:
    python scripts/test_reminder_job.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add server directory to path
sys.path.append(str(Path(__file__).parent.parent / "server"))
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from worker.config import settings
from worker.jobs.reminder_job import send_appointment_reminders
from app.models import Customer, Vehicle, Appointment, CallLog
from app.models.appointment import AppointmentStatus


async def create_test_appointment():
    """Create a test appointment for tomorrow."""
    print("Creating test appointment for tomorrow...")

    engine = create_async_engine(settings.DATABASE_URL)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session_maker() as db:
            # Find or create test customer with YOUR_TEST_NUMBER
            customer_query = select(Customer).where(
                Customer.phone_number == settings.YOUR_TEST_NUMBER
            )
            result = await db.execute(customer_query)
            customer = result.scalar_one_or_none()

            if not customer:
                print(f"Creating test customer with phone: {settings.YOUR_TEST_NUMBER}")
                customer = Customer(
                    name="Test Customer",
                    email="test@example.com",
                    phone_number=settings.YOUR_TEST_NUMBER,
                    address="123 Test St",
                    city="Test City",
                    state="TS",
                    zip_code="12345"
                )
                db.add(customer)
                await db.flush()
            else:
                print(f"Found existing customer: {customer.name} (ID: {customer.id})")

            # Find or create test vehicle
            vehicle_query = select(Vehicle).where(Vehicle.customer_id == customer.id)
            result = await db.execute(vehicle_query)
            vehicle = result.scalar_one_or_none()

            if not vehicle:
                print("Creating test vehicle...")
                vehicle = Vehicle(
                    customer_id=customer.id,
                    vin="1HGBH41JXMN109186",
                    make="Honda",
                    model="Civic",
                    year=2021,
                    color="Blue",
                    license_plate="TEST123"
                )
                db.add(vehicle)
                await db.flush()
            else:
                print(f"Found existing vehicle: {vehicle.year} {vehicle.make} {vehicle.model}")

            # Create appointment for tomorrow at 10 AM
            tomorrow = datetime.now() + timedelta(days=settings.REMINDER_DAYS_BEFORE)
            tomorrow_10am = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

            appointment = Appointment(
                customer_id=customer.id,
                vehicle_id=vehicle.id,
                service_type="Oil Change",
                scheduled_at=tomorrow_10am,
                status=AppointmentStatus.CONFIRMED,
                notes="Test appointment for reminder job"
            )
            db.add(appointment)
            await db.commit()

            print(f"\n✓ Created test appointment:")
            print(f"  - ID: {appointment.id}")
            print(f"  - Customer: {customer.name}")
            print(f"  - Phone: {customer.phone_number}")
            print(f"  - Vehicle: {vehicle.year} {vehicle.make} {vehicle.model}")
            print(f"  - Service: {appointment.service_type}")
            print(f"  - Scheduled: {appointment.scheduled_at}")
            print(f"  - Status: {appointment.status}")

            return appointment.id

    finally:
        await engine.dispose()


async def verify_call_log(appointment_id: str):
    """Verify that a call log was created for the appointment."""
    print("\nVerifying call log...")

    engine = create_async_engine(settings.DATABASE_URL)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session_maker() as db:
            # Wait a moment for the call to be created
            await asyncio.sleep(3)

            # Check for call log
            call_query = select(CallLog).where(
                CallLog.appointment_id == appointment_id
            )
            result = await db.execute(call_query)
            call_logs = result.scalars().all()

            if call_logs:
                print(f"\n✓ Found {len(call_logs)} call log(s):")
                for call in call_logs:
                    print(f"  - Call SID: {call.call_sid}")
                    print(f"  - Direction: {call.direction}")
                    print(f"  - Status: {call.status}")
                    print(f"  - From: {call.from_number}")
                    print(f"  - To: {call.to_number}")
                    print(f"  - Intent: {call.intent}")
                    print(f"  - Started: {call.started_at}")
                return True
            else:
                print("✗ No call logs found")
                return False

    finally:
        await engine.dispose()


async def main():
    """Main test function."""
    print("=" * 60)
    print("Testing Appointment Reminder Job")
    print("=" * 60)

    # Check configuration
    if not settings.YOUR_TEST_NUMBER:
        print("\n✗ ERROR: YOUR_TEST_NUMBER not set in .env")
        print("Please set YOUR_TEST_NUMBER to your phone number for testing")
        return

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        print("\n✗ ERROR: Twilio credentials not set in .env")
        print("Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
        return

    print(f"\n✓ Configuration:")
    print(f"  - Test Number: {settings.YOUR_TEST_NUMBER}")
    print(f"  - Twilio Phone: {settings.TWILIO_PHONE_NUMBER}")
    print(f"  - Server URL: {settings.SERVER_API_URL}")
    print(f"  - Reminder Days Before: {settings.REMINDER_DAYS_BEFORE}")

    # Step 1: Create test appointment
    try:
        appointment_id = await create_test_appointment()
    except Exception as e:
        print(f"\n✗ Failed to create test appointment: {e}")
        return

    # Step 2: Run reminder job
    print("\n" + "=" * 60)
    print("Running Reminder Job")
    print("=" * 60)

    try:
        await send_appointment_reminders()
    except Exception as e:
        print(f"\n✗ Reminder job failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Verify call log
    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)

    success = await verify_call_log(appointment_id)

    if success:
        print("\n" + "=" * 60)
        print("✓ TEST PASSED")
        print("=" * 60)
        print("\nCheck your phone for the reminder call!")
        print(f"You should receive a call at {settings.YOUR_TEST_NUMBER}")
    else:
        print("\n" + "=" * 60)
        print("✗ TEST FAILED")
        print("=" * 60)
        print("\nCall log was not created. Check logs for errors.")


if __name__ == "__main__":
    asyncio.run(main())
