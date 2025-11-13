"""Appointment reminder job."""

import logging
from datetime import datetime, timedelta

# Import models from server
from app.models import Appointment, CallLog, Customer
from app.models.appointment import AppointmentStatus
from app.models.call_log import CallDirection, CallStatus
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from twilio.rest import Client

from worker.config import settings

logger = logging.getLogger(__name__)


async def send_appointment_reminders():
    """
    Find appointments scheduled for tomorrow and initiate reminder calls.
    """
    logger.info("Running appointment reminder job...")

    # Create database connection
    engine = create_async_engine(settings.DATABASE_URL)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session_maker() as db:
            # Calculate tomorrow's date range
            tomorrow_start = datetime.now() + timedelta(days=settings.REMINDER_DAYS_BEFORE)
            tomorrow_start = tomorrow_start.replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow_end = tomorrow_start + timedelta(days=1)

            # Query appointments for tomorrow that are confirmed
            query = select(Appointment).where(
                and_(
                    Appointment.scheduled_at >= tomorrow_start,
                    Appointment.scheduled_at < tomorrow_end,
                    Appointment.status == AppointmentStatus.CONFIRMED,
                )
            )

            result = await db.execute(query)
            appointments = result.scalars().all()

            logger.info(f"Found {len(appointments)} appointments to remind")

            # Initialize Twilio client
            twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            for appointment in appointments:
                try:
                    # Get customer information
                    customer_query = select(Customer).where(Customer.id == appointment.customer_id)
                    customer_result = await db.execute(customer_query)
                    customer = customer_result.scalar_one_or_none()

                    if not customer or not customer.phone_number:
                        logger.warning(
                            f"Skipping appointment {appointment.id}: No customer phone number"
                        )
                        continue

                    # POC SAFETY: Only call YOUR_TEST_NUMBER
                    if (
                        settings.YOUR_TEST_NUMBER
                        and customer.phone_number != settings.YOUR_TEST_NUMBER
                    ):
                        logger.warning(
                            f"Skipping call to {customer.phone_number} (POC safety - only calling {settings.YOUR_TEST_NUMBER})"
                        )
                        continue

                    logger.info(
                        f"Initiating reminder call for appointment {appointment.id} "
                        f"to {customer.phone_number}"
                    )

                    # Initiate outbound call via Twilio
                    # The call will connect to the same WebSocket handler but with
                    # a different prompt template for reminders
                    call = twilio_client.calls.create(
                        to=customer.phone_number,
                        from_=settings.TWILIO_PHONE_NUMBER,
                        url=f"{settings.SERVER_API_URL}/voice/incoming-reminder",
                        status_callback=f"{settings.SERVER_API_URL}/webhooks/twilio/status",
                        status_callback_event=["initiated", "ringing", "answered", "completed"],
                    )

                    # Create call log entry
                    call_log = CallLog(
                        customer_id=customer.id,
                        call_sid=call.sid,
                        direction=CallDirection.OUTBOUND,
                        status=CallStatus.INITIATED,
                        from_number=settings.TWILIO_PHONE_NUMBER,
                        to_number=customer.phone_number,
                        appointment_id=appointment.id,
                        intent="appointment_reminder",
                        started_at=datetime.now(),
                    )
                    db.add(call_log)
                    await db.commit()

                    logger.info(
                        f"Reminder call initiated: {call.sid} for appointment {appointment.id}"
                    )

                except Exception as e:
                    logger.error(f"Failed to send reminder for appointment {appointment.id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error in reminder job: {e}")
    finally:
        await engine.dispose()

    logger.info("Appointment reminder job completed")
