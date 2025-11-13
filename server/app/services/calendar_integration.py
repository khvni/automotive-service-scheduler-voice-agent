"""
Calendar Integration Layer for CRM Tools.

This module bridges CRM appointment management with Google Calendar,
ensuring appointments are created in both the database and calendar.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Appointment, Customer, Vehicle
from app.services.calendar_service import CalendarService

logger = logging.getLogger(__name__)


async def book_appointment_with_calendar(
    db: AsyncSession,
    calendar: CalendarService,
    customer_id: int,
    vehicle_id: int,
    service_type: str,
    start_time: datetime,
    duration_minutes: int = 60,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Book appointment in both Google Calendar and CRM database.

    This function:
    1. Fetches customer and vehicle details
    2. Creates calendar event with customer info
    3. Creates database appointment record linked to calendar event
    4. Returns combined result

    Args:
        db: Database session
        calendar: CalendarService instance
        customer_id: Customer ID
        vehicle_id: Vehicle ID
        service_type: Type of service (e.g., "Oil Change", "Brake Inspection")
        start_time: Appointment start time
        duration_minutes: Duration in minutes (default: 60)
        notes: Additional notes (optional)

    Returns:
        Dictionary with appointment and calendar details:
        {
            'success': True,
            'appointment_id': 'uuid',
            'calendar_event_id': 'google_event_id',
            'calendar_link': 'https://calendar.google.com/...',
            'customer_name': 'John Doe',
            'vehicle_info': '2020 Honda Civic',
            'start_time': '2025-11-15T10:00:00',
            'message': 'Appointment booked successfully'
        }

    Raises:
        Exception: If booking fails
    """
    try:
        # Fetch customer details
        customer_result = await db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        customer = customer_result.scalar_one_or_none()

        if not customer:
            return {
                'success': False,
                'message': f'Customer with ID {customer_id} not found'
            }

        # Fetch vehicle details
        vehicle_result = await db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id)
        )
        vehicle = vehicle_result.scalar_one_or_none()

        if not vehicle:
            return {
                'success': False,
                'message': f'Vehicle with ID {vehicle_id} not found'
            }

        customer_name = f"{customer.first_name} {customer.last_name}"
        vehicle_info = f"{vehicle.year} {vehicle.make} {vehicle.model}"

        # Create calendar event
        end_time = start_time + timedelta(minutes=duration_minutes)

        event_title = f"{service_type} - {customer_name}"
        event_description = (
            f"Customer: {customer_name}\n"
            f"Phone: {customer.phone_number}\n"
            f"Email: {customer.email or 'N/A'}\n"
            f"Vehicle: {vehicle_info}\n"
            f"VIN: {vehicle.vin}\n"
            f"Service Type: {service_type}\n"
        )

        if notes:
            event_description += f"\nNotes: {notes}"

        calendar_result = await calendar.create_calendar_event(
            title=event_title,
            start_time=start_time,
            end_time=end_time,
            description=event_description,
            attendees=[customer.email] if customer.email else None
        )

        if not calendar_result['success']:
            logger.error(f"Failed to create calendar event: {calendar_result['message']}")
            return {
                'success': False,
                'message': f"Failed to create calendar event: {calendar_result['message']}"
            }

        # Create database appointment
        appointment_id = uuid.uuid4()
        appointment = Appointment(
            id=appointment_id,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            service_type=service_type,
            scheduled_at=start_time,
            duration_minutes=duration_minutes,
            status='scheduled',
            calendar_event_id=calendar_result['event_id'],
            notes=notes
        )

        db.add(appointment)
        await db.commit()
        await db.refresh(appointment)

        logger.info(f"Appointment booked: {appointment_id} with calendar event {calendar_result['event_id']}")

        return {
            'success': True,
            'appointment_id': str(appointment_id),
            'calendar_event_id': calendar_result['event_id'],
            'calendar_link': calendar_result['calendar_link'],
            'customer_name': customer_name,
            'vehicle_info': vehicle_info,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'service_type': service_type,
            'message': f"Appointment for {service_type} booked successfully"
        }

    except Exception as e:
        logger.error(f"Error booking appointment with calendar: {e}", exc_info=True)
        await db.rollback()
        return {
            'success': False,
            'message': f"Failed to book appointment: {str(e)}"
        }


async def reschedule_appointment_with_calendar(
    db: AsyncSession,
    calendar: CalendarService,
    appointment_id: str,
    new_start_time: datetime,
    new_duration_minutes: Optional[int] = None
) -> Dict[str, Any]:
    """
    Reschedule appointment in both calendar and database.

    Args:
        db: Database session
        calendar: CalendarService instance
        appointment_id: Appointment UUID
        new_start_time: New start time
        new_duration_minutes: New duration (optional, keeps existing if None)

    Returns:
        Dictionary with update result

    Raises:
        Exception: If rescheduling fails
    """
    try:
        # Fetch appointment
        appointment_result = await db.execute(
            select(Appointment).where(Appointment.id == uuid.UUID(appointment_id))
        )
        appointment = appointment_result.scalar_one_or_none()

        if not appointment:
            return {
                'success': False,
                'message': f'Appointment {appointment_id} not found'
            }

        # Determine duration
        duration = new_duration_minutes if new_duration_minutes else appointment.duration_minutes
        new_end_time = new_start_time + timedelta(minutes=duration)

        # Update calendar event if calendar_event_id exists
        if appointment.calendar_event_id:
            calendar_result = await calendar.update_calendar_event(
                event_id=appointment.calendar_event_id,
                start_time=new_start_time,
                end_time=new_end_time
            )

            if not calendar_result['success']:
                logger.error(f"Failed to update calendar event: {calendar_result['message']}")
                return {
                    'success': False,
                    'message': f"Failed to update calendar: {calendar_result['message']}"
                }

        # Update database appointment
        appointment.scheduled_at = new_start_time
        if new_duration_minutes:
            appointment.duration_minutes = new_duration_minutes

        await db.commit()
        await db.refresh(appointment)

        logger.info(f"Appointment rescheduled: {appointment_id} to {new_start_time}")

        return {
            'success': True,
            'appointment_id': appointment_id,
            'new_start_time': new_start_time.isoformat(),
            'new_end_time': new_end_time.isoformat(),
            'message': 'Appointment rescheduled successfully'
        }

    except Exception as e:
        logger.error(f"Error rescheduling appointment: {e}", exc_info=True)
        await db.rollback()
        return {
            'success': False,
            'message': f"Failed to reschedule appointment: {str(e)}"
        }


async def cancel_appointment_with_calendar(
    db: AsyncSession,
    calendar: CalendarService,
    appointment_id: str
) -> Dict[str, Any]:
    """
    Cancel appointment in both calendar and database.

    Args:
        db: Database session
        calendar: CalendarService instance
        appointment_id: Appointment UUID

    Returns:
        Dictionary with cancellation result

    Raises:
        Exception: If cancellation fails
    """
    try:
        # Fetch appointment
        appointment_result = await db.execute(
            select(Appointment).where(Appointment.id == uuid.UUID(appointment_id))
        )
        appointment = appointment_result.scalar_one_or_none()

        if not appointment:
            return {
                'success': False,
                'message': f'Appointment {appointment_id} not found'
            }

        # Cancel calendar event if exists
        if appointment.calendar_event_id:
            calendar_result = await calendar.cancel_calendar_event(
                event_id=appointment.calendar_event_id
            )

            if not calendar_result['success']:
                logger.warning(f"Failed to cancel calendar event: {calendar_result['message']}")
                # Continue with database update even if calendar fails

        # Update database appointment status
        appointment.status = 'cancelled'
        await db.commit()
        await db.refresh(appointment)

        logger.info(f"Appointment cancelled: {appointment_id}")

        return {
            'success': True,
            'appointment_id': appointment_id,
            'message': 'Appointment cancelled successfully'
        }

    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}", exc_info=True)
        await db.rollback()
        return {
            'success': False,
            'message': f"Failed to cancel appointment: {str(e)}"
        }


async def get_available_slots_for_date(
    calendar: CalendarService,
    date: datetime,
    slot_duration_minutes: int = 30,
    start_hour: int = 9,
    end_hour: int = 17
) -> Dict[str, Any]:
    """
    Get available time slots for a specific date.

    Args:
        calendar: CalendarService instance
        date: Date to check (time component ignored)
        slot_duration_minutes: Minimum slot duration (default: 30)
        start_hour: Business day start hour (default: 9 AM)
        end_hour: Business day end hour (default: 5 PM)

    Returns:
        Dictionary with available slots:
        {
            'success': True,
            'date': '2025-11-15',
            'available_slots': [
                {'start': '2025-11-15T09:00:00', 'end': '2025-11-15T12:00:00'},
                {'start': '2025-11-15T13:00:00', 'end': '2025-11-15T17:00:00'}
            ],
            'count': 2
        }

    Raises:
        Exception: If availability check fails
    """
    try:
        # Set time boundaries for the day
        start_time = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

        # Ensure times are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=calendar.timezone)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=calendar.timezone)

        # Get free slots
        free_slots = await calendar.get_free_availability(
            start_time=start_time,
            end_time=end_time,
            duration_minutes=slot_duration_minutes
        )

        # Format slots for response
        formatted_slots = [
            {
                'start': slot['start'].isoformat(),
                'end': slot['end'].isoformat(),
                'start_formatted': slot['start'].strftime('%I:%M %p'),
                'end_formatted': slot['end'].strftime('%I:%M %p')
            }
            for slot in free_slots
        ]

        logger.info(f"Found {len(free_slots)} available slots for {date.date()}")

        return {
            'success': True,
            'date': date.date().isoformat(),
            'available_slots': formatted_slots,
            'count': len(formatted_slots),
            'message': f"Found {len(formatted_slots)} available time slots"
        }

    except Exception as e:
        logger.error(f"Error getting available slots: {e}", exc_info=True)
        return {
            'success': False,
            'date': date.date().isoformat(),
            'available_slots': [],
            'count': 0,
            'message': f"Failed to get availability: {str(e)}"
        }


async def get_customer_appointments(
    db: AsyncSession,
    customer_id: int,
    include_past: bool = False
) -> List[Dict[str, Any]]:
    """
    Get all appointments for a customer.

    Args:
        db: Database session
        customer_id: Customer ID
        include_past: Include past appointments (default: False)

    Returns:
        List of appointment dictionaries

    Raises:
        Exception: If query fails
    """
    try:
        query = select(Appointment).where(Appointment.customer_id == customer_id)

        if not include_past:
            query = query.where(Appointment.scheduled_at >= datetime.now())

        query = query.order_by(Appointment.scheduled_at.desc())

        result = await db.execute(query)
        appointments = result.scalars().all()

        return [
            {
                'id': str(appointment.id),
                'service_type': appointment.service_type,
                'scheduled_at': appointment.scheduled_at.isoformat(),
                'duration_minutes': appointment.duration_minutes,
                'status': appointment.status,
                'calendar_event_id': appointment.calendar_event_id,
                'notes': appointment.notes
            }
            for appointment in appointments
        ]

    except Exception as e:
        logger.error(f"Error getting customer appointments: {e}", exc_info=True)
        return []
