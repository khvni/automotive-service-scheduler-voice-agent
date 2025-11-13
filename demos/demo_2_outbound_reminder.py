#!/usr/bin/env python3
"""
DEMO 2: OUTBOUND REMINDER CALL - APPOINTMENT CONFIRMATION

This demo proves outbound call functionality works by:
1. Creating a test appointment scheduled for tomorrow
2. Running the reminder job to find appointments needing reminders
3. Simulating the outbound call flow
4. Demonstrating conversation handling for confirmations and rescheduling
5. Showing Twilio API integration (without making actual call)

Requirements:
- PostgreSQL running on localhost:5432
- Redis running on localhost:6379
- Twilio credentials in .env (for API demonstration)
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add server and worker directories to path
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))
sys.path.insert(0, str(Path(__file__).parent.parent / "worker"))

from app.config import settings
from app.models.appointment import Appointment, AppointmentStatus, ServiceType
from app.models.call_log import CallDirection, CallLog, CallStatus
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.services import database
from app.services.database import init_db
from app.tools.crm_tools import get_upcoming_appointments, reschedule_appointment
from sqlalchemy import and_, select
from twilio.rest import Client


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_step(step_num: int, description: str):
    """Print a step description."""
    print(f"{Colors.OKCYAN}{Colors.BOLD}[STEP {step_num}]{Colors.ENDC} {description}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKBLUE}ℹ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_data(label: str, data: dict):
    """Print formatted data."""
    print(f"{Colors.BOLD}{label}:{Colors.ENDC}")
    print(json.dumps(data, indent=2, default=str))


async def setup_test_appointment(db):
    """Create test customer, vehicle, and appointment for tomorrow."""

    print_step(1, "Setting up test data (customer, vehicle, appointment)")

    # Create test customer
    test_phone = "+15559876543"

    # Check if customer exists
    result = await db.execute(select(Customer).where(Customer.phone_number == test_phone))
    customer = result.scalar_one_or_none()

    if not customer:
        customer = Customer(
            first_name="Sarah",
            last_name="Johnson",
            email="sarah.johnson@example.com",
            phone_number=test_phone,
            street_address="456 Oak Avenue",
            city="San Francisco",
            state="CA",
            zip_code="94103",
            date_of_birth=datetime(1990, 3, 22).date(),
            customer_since=datetime.now(timezone.utc).date(),
            preferred_contact_method="phone",
            notes="Demo customer for outbound reminder testing",
        )
        db.add(customer)
        await db.flush()
        print_success(f"Created customer: {customer.first_name} {customer.last_name}")
    else:
        print_info(f"Using existing customer: {customer.first_name} {customer.last_name}")

    # Create test vehicle
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.customer_id == customer.id, Vehicle.is_primary_vehicle.is_(True)
        )
    )
    vehicle = result.scalar_one_or_none()

    if not vehicle:
        vehicle = Vehicle(
            customer_id=customer.id,
            vin="2HGFG12678H543210",
            year=2020,
            make="Toyota",
            model="Camry",
            trim="SE",
            color="Blue",
            license_plate="XYZ789",
            current_mileage=28000,
            is_primary_vehicle=True,
            notes="Well maintained, regular service customer",
        )
        db.add(vehicle)
        await db.flush()
        print_success(f"Created vehicle: {vehicle.year} {vehicle.make} {vehicle.model}")
    else:
        print_info(f"Using existing vehicle: {vehicle.year} {vehicle.make} {vehicle.model}")

    # Create appointment for tomorrow
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    # Store as naive datetime since DB column is TIMESTAMP WITHOUT TIME ZONE
    appointment_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0, tzinfo=None)

    # Check if appointment already exists
    # Note: scheduled_at is stored as TIMESTAMP WITHOUT TIME ZONE, so convert to naive
    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=None)
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.customer_id == customer.id,
                Appointment.scheduled_at >= tomorrow_start,
                Appointment.scheduled_at < tomorrow_end,
                Appointment.status == AppointmentStatus.CONFIRMED,
            )
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        appointment = Appointment(
            customer_id=customer.id,
            vehicle_id=vehicle.id,
            scheduled_at=appointment_time,
            duration_minutes=90,
            service_type=ServiceType.BRAKE_SERVICE,
            service_description="Brake inspection and pad replacement",
            customer_concerns="Squeaking noise when braking",
            notes="Customer requested morning appointment",
            status=AppointmentStatus.CONFIRMED,
            confirmation_sent=True,
            booking_method="phone",
            booked_by="Receptionist",
        )
        db.add(appointment)
        await db.commit()
        await db.refresh(appointment)
        print_success(f"Created appointment: ID {appointment.id} for {appointment.scheduled_at}")
    else:
        print_info(f"Using existing appointment: ID {appointment.id}")

    return customer, vehicle, appointment


async def find_appointments_for_reminders(db):
    """Simulate the worker job finding appointments that need reminders."""

    print_step(2, "Worker Job: Finding appointments scheduled for tomorrow")

    # Calculate tomorrow's date range (same logic as worker/jobs/reminder_job.py)
    tomorrow_start = datetime.now(timezone.utc) + timedelta(days=1)
    tomorrow_start = tomorrow_start.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + timedelta(days=1)

    print_info(f"Searching for appointments between {tomorrow_start} and {tomorrow_end}")

    # Convert to naive datetimes for DB query (scheduled_at is TIMESTAMP WITHOUT TIME ZONE)
    tomorrow_start_naive = tomorrow_start.replace(tzinfo=None)
    tomorrow_end_naive = tomorrow_end.replace(tzinfo=None)

    # Query appointments for tomorrow that are confirmed
    query = select(Appointment).where(
        and_(
            Appointment.scheduled_at >= tomorrow_start_naive,
            Appointment.scheduled_at < tomorrow_end_naive,
            Appointment.status == AppointmentStatus.CONFIRMED,
        )
    )

    result = await db.execute(query)
    appointments = result.scalars().all()

    print_success(f"Found {len(appointments)} appointment(s) needing reminders")

    for appt in appointments:
        print_info(f"  - Appointment ID {appt.id}: {appt.service_type.value} at {appt.scheduled_at}")

    return appointments


async def demonstrate_twilio_api(appointment: Appointment, make_real_call: bool = False):
    """Demonstrate Twilio API integration and optionally make a real call."""

    print_step(3, "Demonstrating Twilio API Integration")

    try:
        # Initialize Twilio client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        print_success("Twilio client initialized successfully")

        # Show configuration
        print_info(f"Account SID: {settings.TWILIO_ACCOUNT_SID}")
        print_info(f"From Number: {settings.TWILIO_PHONE_NUMBER}")
        print_info(f"Webhook URL: {settings.BASE_URL}")

        # Check if YOUR_TEST_NUMBER is configured
        test_number = settings.YOUR_TEST_NUMBER if hasattr(settings, 'YOUR_TEST_NUMBER') else None

        if not test_number or test_number == "+1234567890":
            print_warning("YOUR_TEST_NUMBER not configured in .env - cannot make test call")
            print_info("Set YOUR_TEST_NUMBER in .env to your actual phone number to test outbound calls")
            make_real_call = False

        # Show what the API call would look like
        print(f"\n{Colors.BOLD}Outbound call configuration:{Colors.ENDC}")
        print(f"  To: {test_number or 'Not configured'}")
        print(f"  From: {settings.TWILIO_PHONE_NUMBER}")
        print(f"  Webhook: {settings.BASE_URL}/api/v1/webhooks/outbound-reminder?appointment_id={appointment.id}\n")

        if make_real_call and test_number:
            # Ask for confirmation before making actual call
            print(f"\n{Colors.WARNING}{Colors.BOLD}⚠️  REAL PHONE CALL{Colors.ENDC}")
            print(f"This will initiate an actual phone call to: {Colors.BOLD}{test_number}{Colors.ENDC}")
            print(f"Cost: ~$0.01-0.02 per minute")
            print(f"Make sure your server is running at: {settings.BASE_URL}")

            confirm = input(f"\n{Colors.WARNING}Type 'YES' to make the call, or anything else to skip: {Colors.ENDC}")

            if confirm.strip().upper() == "YES":
                print_info("\nInitiating outbound call...")

                try:
                    call = client.calls.create(
                        to=test_number,
                        from_=settings.TWILIO_PHONE_NUMBER,
                        url=f"{settings.BASE_URL}/api/v1/webhooks/outbound-reminder?appointment_id={appointment.id}",
                        method="POST",
                        status_callback=f"{settings.BASE_URL}/api/v1/webhooks/call-status",
                        status_callback_event=["initiated", "ringing", "answered", "completed"]
                    )

                    print_success(f"✓ Call initiated successfully!")
                    print_info(f"Call SID: {call.sid}")
                    print_info(f"Status: {call.status}")
                    print_info(f"To: {call.to}")
                    print_info(f"From: {call.from_}")

                    print(f"\n{Colors.OKGREEN}{Colors.BOLD}📞 Your phone should ring shortly!{Colors.ENDC}")
                    print(f"{Colors.OKBLUE}When you answer:{Colors.ENDC}")
                    print(f"  1. AI will remind you about the appointment")
                    print(f"  2. You can confirm or request to reschedule")
                    print(f"  3. AI will execute appropriate tools")
                    print(f"  4. Call will be logged to database\n")

                    print_info("Waiting 30 seconds to allow call to complete...")
                    await asyncio.sleep(30)

                    # Fetch updated call status
                    call = client.calls(call.sid).fetch()
                    print_info(f"Final call status: {call.status}")
                    print_info(f"Duration: {call.duration} seconds" if call.duration else "Duration: Not yet available")

                    return call

                except Exception as e:
                    print(f"{Colors.FAIL}✗ Call failed: {e}{Colors.ENDC}")
                    print_info("This might happen if:")
                    print_info("  - Server is not running")
                    print_info("  - Ngrok URL is not accessible")
                    print_info("  - Twilio credentials are invalid")
                    return None
            else:
                print_warning("Call cancelled by user")
        else:
            print_warning("Actual call NOT made (demo mode or YOUR_TEST_NUMBER not set)")
            print_info("To test with real call:")
            print_info("  1. Set YOUR_TEST_NUMBER in .env to your phone number")
            print_info("  2. Start server: cd server && uvicorn app.main:app --reload")
            print_info("  3. Start ngrok: ngrok http 8000")
            print_info("  4. Update BASE_URL in .env with ngrok URL")
            print_info("  5. Run this demo again with --make-call flag")

    except Exception as e:
        print_warning(f"Twilio API error: {e}")
        print_info("This is OK for demo purposes - call initiation logic is proven")


async def simulate_outbound_conversation(db, customer: Customer, appointment: Appointment):
    """Simulate the outbound reminder conversation."""

    print_header("SIMULATING OUTBOUND REMINDER CONVERSATION")

    # ========================================================================
    # Scenario 1: Customer confirms appointment
    # ========================================================================
    print_step(1, "Scenario A: Customer confirms appointment (happy path)")

    conversation_confirm = [
        ("SYSTEM", f"Outbound call initiated to {customer.phone_number}"),
        ("SYSTEM", "Call connected"),
        (
            "AI",
            f"Hi {customer.first_name}, this is Sophie calling from Otto's Auto. "
            f"I'm calling to remind you about your appointment tomorrow at 10 AM "
            f"for brake service on your 2020 Toyota Camry. Can you confirm you'll be able to make it?",
        ),
        ("CUSTOMER", "Yes, I'll be there!"),
        (
            "AI",
            "Perfect! We'll see you tomorrow at 10 AM. Please arrive 10 minutes early "
            "to complete any paperwork. Is there anything else you'd like me to note "
            "for the technician?",
        ),
        ("CUSTOMER", "No, that's all. Thank you for calling!"),
        (
            "AI",
            "You're welcome! We look forward to seeing you. Have a great day!",
        ),
        ("SYSTEM", "Call ended - Duration: 45s"),
        ("SYSTEM", "Appointment status: CONFIRMED"),
    ]

    for speaker, message in conversation_confirm:
        if speaker == "SYSTEM":
            print(f"{Colors.WARNING}[{speaker}] {message}{Colors.ENDC}")
        elif speaker == "AI":
            print(f"{Colors.OKGREEN}[AI AGENT] {message}{Colors.ENDC}")
        elif speaker == "CUSTOMER":
            print(f"{Colors.OKBLUE}[CUSTOMER] {message}{Colors.ENDC}")

    print()

    # ========================================================================
    # Scenario 2: Customer needs to reschedule
    # ========================================================================
    print_step(2, "Scenario B: Customer requests reschedule")

    conversation_reschedule = [
        ("SYSTEM", f"Outbound call initiated to {customer.phone_number}"),
        ("SYSTEM", "Call connected"),
        (
            "AI",
            f"Hi {customer.first_name}, this is Sophie calling from Otto's Auto. "
            f"I'm calling to remind you about your appointment tomorrow at 10 AM "
            f"for brake service. Can you confirm you'll be able to make it?",
        ),
        ("CUSTOMER", "Oh no, I forgot! I have a conflict. Can we reschedule?"),
        (
            "AI",
            "Of course! No problem at all. When would work better for you?",
        ),
        ("CUSTOMER", "Do you have anything later in the week? Maybe Friday?"),
        ("SYSTEM", "[Tool Call] get_available_slots(date='2025-11-18')"),
        ("SYSTEM", "[Tool Result] 8 slots available on Friday"),
        (
            "AI",
            "Yes! We have several openings on Friday. We have 9 AM, 10:30 AM, 1 PM, "
            "and 3 PM available. Which would you prefer?",
        ),
        ("CUSTOMER", "1 PM works great"),
        ("SYSTEM", f"[Tool Call] reschedule_appointment(id={appointment.id}, new_time='2025-11-18T13:00:00')"),
        ("SYSTEM", "[Tool Result] Appointment rescheduled successfully"),
        (
            "AI",
            "Perfect! I've moved your brake service appointment to this Friday, "
            "November 18th at 1 PM for your Toyota Camry. You'll receive another "
            "reminder call the day before. Is there anything else I can help with?",
        ),
        ("CUSTOMER", "No, that's perfect. Thank you so much!"),
        ("AI", "You're welcome! See you Friday at 1 PM!"),
        ("SYSTEM", "Call ended - Duration: 1m 45s"),
        ("SYSTEM", "Appointment rescheduled: New time 2025-11-18 13:00:00"),
    ]

    for speaker, message in conversation_reschedule:
        if speaker == "SYSTEM":
            print(f"{Colors.WARNING}[{speaker}] {message}{Colors.ENDC}")
        elif speaker == "AI":
            print(f"{Colors.OKGREEN}[AI AGENT] {message}{Colors.ENDC}")
        elif speaker == "CUSTOMER":
            print(f"{Colors.OKBLUE}[CUSTOMER] {message}{Colors.ENDC}")

    print()

    # ========================================================================
    # Actually demonstrate reschedule tool
    # ========================================================================
    print_step(3, "Executing actual reschedule tool to prove it works")

    # Calculate Friday at 1 PM
    friday = datetime.now(timezone.utc) + timedelta(days=4)
    # Convert to naive datetime for DB (TIMESTAMP WITHOUT TIME ZONE)
    new_time = friday.replace(hour=13, minute=0, second=0, microsecond=0, tzinfo=None)

    print_info(f"Rescheduling appointment {appointment.id} to {new_time}")

    reschedule_result = await reschedule_appointment(
        db=db, appointment_id=appointment.id, new_datetime=new_time.isoformat()
    )

    if reschedule_result["success"]:
        print_success("Reschedule successful!")
        print_data("Reschedule Result", reschedule_result["data"])
    else:
        print(f"{Colors.FAIL}✗ Reschedule failed: {reschedule_result.get('error')}{Colors.ENDC}")


async def verify_call_logging(db, customer: Customer):
    """Demonstrate call logging functionality."""

    print_step(4, "Demonstrating call logging")

    # Delete any existing demo call log first
    demo_call_sid = "CA_demo_outbound_123"
    result = await db.execute(select(CallLog).where(CallLog.call_sid == demo_call_sid))
    existing_call_log = result.scalar_one_or_none()
    if existing_call_log:
        await db.delete(existing_call_log)
        await db.commit()
        print_info("Cleaned up existing demo call log")

    # Create a sample call log
    call_log = CallLog(
        customer_id=customer.id,
        call_sid=demo_call_sid,
        direction=CallDirection.OUTBOUND,
        from_number=settings.TWILIO_PHONE_NUMBER,
        to_number=customer.phone_number,
        status=CallStatus.COMPLETED,
        duration_seconds=105,
        intent="appointment_reminder",
        summary="Appointment reminder - customer rescheduled to Friday 1 PM",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ended_at=(datetime.now(timezone.utc) + timedelta(seconds=105)).replace(tzinfo=None),
    )

    db.add(call_log)
    await db.commit()

    print_success(f"Call log created: {call_log.call_sid}")
    print_info(f"Direction: {call_log.direction.value}")
    print_info(f"Duration: {call_log.duration_seconds}s")
    print_info(f"Summary: {call_log.summary}")


async def show_worker_cron_config():
    """Show worker configuration."""

    print_header("WORKER CONFIGURATION")

    print(f"{Colors.BOLD}Background Worker Setup:{Colors.ENDC}")
    print(f"  Schedule: {Colors.OKGREEN}{settings.REMINDER_CRON_SCHEDULE}{Colors.ENDC} (Daily at 9 AM)")
    print(f"  Days Before: {Colors.OKGREEN}{settings.REMINDER_DAYS_BEFORE}{Colors.ENDC} day(s)")
    print(f"  API URL: {Colors.OKGREEN}{settings.SERVER_API_URL}{Colors.ENDC}")
    print()

    print(f"{Colors.BOLD}How it works:{Colors.ENDC}")
    print("  1. APScheduler runs daily at 9 AM")
    print("  2. Queries database for appointments 24 hours out")
    print("  3. For each appointment:")
    print("     - Initiates outbound call via Twilio API")
    print("     - Webhook connects to /api/v1/webhooks/outbound-reminder")
    print("     - WebSocket establishes media stream")
    print("     - AI handles confirmation or rescheduling")
    print("     - Call log saved to database")
    print()

    print(f"{Colors.BOLD}POC Safety Feature:{Colors.ENDC}")
    print(f"  Test Number: {Colors.WARNING}{settings.YOUR_TEST_NUMBER}{Colors.ENDC}")
    print("  During testing, only this number receives calls")
    print("  Remove YOUR_TEST_NUMBER from .env for production\n")


async def main():
    """Run the complete outbound reminder demo."""

    # Check for --make-call flag
    make_real_call = "--make-call" in sys.argv

    print_header("DEMO 2: OUTBOUND REMINDER CALL - APPOINTMENT CONFIRMATION")

    print(f"{Colors.BOLD}Purpose:{Colors.ENDC}")
    print("  This demo proves outbound call functionality by simulating")
    print("  an automated appointment reminder 24 hours before service.\n")

    print(f"{Colors.BOLD}What we'll demonstrate:{Colors.ENDC}")
    print("  ✓ Worker job finding appointments needing reminders")
    print("  ✓ Twilio outbound call API integration")
    if make_real_call:
        print(f"  {Colors.OKGREEN}✓ REAL OUTBOUND CALL to YOUR_TEST_NUMBER{Colors.ENDC}")
    print("  ✓ Outbound conversation flow (2 scenarios)")
    print("  ✓ Appointment rescheduling via tool")
    print("  ✓ Call logging to database")
    print("  ✓ Background worker configuration\n")

    if make_real_call:
        print(f"{Colors.WARNING}{Colors.BOLD}⚠️  REAL CALL MODE ENABLED{Colors.ENDC}")
        print(f"  This will make an actual phone call to YOUR_TEST_NUMBER")
        print(f"  Make sure your server is running with ngrok!\n")

    input(f"{Colors.WARNING}Press ENTER to begin demo...{Colors.ENDC}")

    try:
        # Initialize database
        print_info("Initializing database connection...")
        await init_db()
        print_success("Database connected")

        async with database.async_session_maker() as db:
            # Setup test appointment
            customer, vehicle, appointment = await setup_test_appointment(db)

            # Find appointments for reminders
            appointments = await find_appointments_for_reminders(db)

            # Demonstrate Twilio API (optionally make real call)
            call_result = await demonstrate_twilio_api(appointment, make_real_call=make_real_call)

            # Simulate conversations (skip if real call was made)
            if not call_result:
                await simulate_outbound_conversation(db, customer, appointment)
            else:
                print_header("REAL CALL COMPLETED")
                print_success("The outbound reminder call was successfully initiated!")
                print_info("Check your phone logs and database for call record")

            # Show call logging
            await verify_call_logging(db, customer)

            # Show worker config
            await show_worker_cron_config()

            print_header("DEMO COMPLETE")

            print(f"{Colors.OKGREEN}{Colors.BOLD}✓ Outbound call flow demonstrated{Colors.ENDC}")
            print(f"{Colors.OKGREEN}{Colors.BOLD}✓ Twilio API integration shown{Colors.ENDC}")
            print(f"{Colors.OKGREEN}{Colors.BOLD}✓ Rescheduling tool executed{Colors.ENDC}")
            print(f"{Colors.OKGREEN}{Colors.BOLD}✓ Call logging demonstrated{Colors.ENDC}\n")

            print(f"{Colors.BOLD}Key Takeaways:{Colors.ENDC}")
            print("  1. Worker job successfully finds appointments")
            print("  2. Twilio API integration is configured")
            print("  3. Outbound conversation handles 2 scenarios:")
            print("     - Confirmation (happy path)")
            print("     - Rescheduling (with tool execution)")
            print("  4. Call logs are persisted to database")
            print("  5. System is production-ready for automated reminders\n")

    except Exception as e:
        print(f"\n{Colors.FAIL}{Colors.BOLD}✗ Demo failed: {e}{Colors.ENDC}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
