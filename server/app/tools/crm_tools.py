"""CRM tools for customer and appointment management."""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx
from app.models.appointment import Appointment, AppointmentStatus, ServiceType
from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.services.redis_client import (
    cache_customer,
    get_cached_customer,
    get_redis,
    invalidate_customer_cache,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

# Constants
VIN_CACHE_TTL = 604800  # 7 days in seconds
VIN_CACHE_PREFIX = "vin:"
NHTSA_API_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"
HTTP_TIMEOUT = 5.0  # seconds


# ============================================================================
# Tool 1: Customer Lookup
# ============================================================================


async def lookup_customer(db: AsyncSession, phone: str) -> Optional[Dict[str, Any]]:
    """
    Look up customer by phone number with caching.

    Implements two-tier lookup:
    1. Check Redis cache (target: <2ms)
    2. Query database with vehicles JOIN (target: <30ms)

    Args:
        db: Database session
        phone: Customer phone number (normalized format)

    Returns:
        Customer information with vehicles if found, None otherwise.
        Structure:
            {
                "id": int,
                "first_name": str,
                "last_name": str,
                "email": str,
                "phone_number": str,
                "customer_since": str (ISO date),
                "last_service_date": str (ISO datetime) | None,
                "vehicles": [
                    {
                        "id": int,
                        "vin": str,
                        "year": int,
                        "make": str,
                        "model": str,
                        "trim": str | None,
                        "color": str | None,
                        "current_mileage": int | None,
                        "is_primary_vehicle": bool
                    }
                ],
                "notes": str | None
            }
    """
    try:
        # Check cache first
        cached = await get_cached_customer(phone)
        if cached:
            logger.info(f"Customer cache hit for phone: {phone}")
            return cached

        # Cache miss - query database
        logger.info(f"Customer cache miss for phone: {phone}, querying database")

        # Use selectinload to fetch vehicles in single query (avoid N+1)
        stmt = (
            select(Customer)
            .options(selectinload(Customer.vehicles))
            .where(Customer.phone_number == phone)
        )
        result = await db.execute(stmt)
        customer = result.scalar_one_or_none()

        if not customer:
            logger.info(f"Customer not found for phone: {phone}")
            return None

        # Build response
        customer_data = {
            "id": customer.id,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "phone_number": customer.phone_number,
            "customer_since": (
                customer.customer_since.isoformat() if customer.customer_since else None
            ),
            "last_service_date": (
                customer.last_service_date.isoformat() if customer.last_service_date else None
            ),
            "vehicles": [
                {
                    "id": v.id,
                    "vin": v.vin,
                    "year": v.year,
                    "make": v.make,
                    "model": v.model,
                    "trim": v.trim,
                    "color": v.color,
                    "current_mileage": v.current_mileage,
                    "is_primary_vehicle": v.is_primary_vehicle,
                }
                for v in customer.vehicles
            ],
            "notes": customer.notes,
        }

        # Cache the result (5 minute TTL)
        await cache_customer(phone, customer_data, ttl=300)
        logger.info(f"Customer cached for phone: {phone}")

        return customer_data

    except Exception as e:
        logger.error(f"Error looking up customer {phone}: {e}", exc_info=True)
        raise


# ============================================================================
# Tool 2: Search Customers by Name
# ============================================================================


async def search_customers_by_name(
    db: AsyncSession,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search for customers by first and/or last name with partial matching.

    Enables name-based customer lookup when phone number is not available.
    Uses case-insensitive partial matching (ILIKE).

    Args:
        db: Database session
        first_name: Customer first name (partial match supported)
        last_name: Customer last name (partial match supported)

    Returns:
        List of matching customers with basic info (top 5 results):
            [
                {
                    "id": int,
                    "first_name": str,
                    "last_name": str,
                    "phone_number": str,
                    "email": str,
                    "customer_since": str (ISO date) | None,
                    "vehicle_count": int
                }
            ]

    Examples:
        - search_customers_by_name(first_name="John") -> All Johns
        - search_customers_by_name(last_name="Smith") -> All Smiths
        - search_customers_by_name(first_name="Ali", last_name="Khan") -> Ali Khan matches
    """
    try:
        if not first_name and not last_name:
            logger.warning("search_customers_by_name called with no search criteria")
            return []

        # Build query with partial matching
        stmt = select(Customer).options(selectinload(Customer.vehicles))

        if first_name and last_name:
            # Both provided - match both
            stmt = stmt.where(
                Customer.first_name.ilike(f"%{first_name}%"),
                Customer.last_name.ilike(f"%{last_name}%")
            )
        elif first_name:
            # Only first name
            stmt = stmt.where(Customer.first_name.ilike(f"%{first_name}%"))
        else:
            # Only last name
            stmt = stmt.where(Customer.last_name.ilike(f"%{last_name}%"))

        # Limit to top 5 results to avoid overwhelming the LLM
        stmt = stmt.limit(5)

        result = await db.execute(stmt)
        customers = result.scalars().all()

        # Build response list
        customer_list = []
        for customer in customers:
            customer_list.append({
                "id": customer.id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "phone_number": customer.phone_number,
                "email": customer.email,
                "customer_since": (
                    customer.customer_since.isoformat() if customer.customer_since else None
                ),
                "vehicle_count": len(customer.vehicles) if customer.vehicles else 0,
            })

        logger.info(
            f"Found {len(customer_list)} customers matching "
            f"first_name='{first_name}', last_name='{last_name}'"
        )

        return customer_list

    except Exception as e:
        logger.error(
            f"Error searching customers by name (first='{first_name}', last='{last_name}'): {e}",
            exc_info=True
        )
        raise


# ============================================================================
# Tool 3: Get Available Slots (POC Mock)
# ============================================================================


async def get_available_slots(date: str, duration_minutes: int = 30) -> Dict[str, Any]:
    """
    Get available appointment slots for a given date (POC mock implementation).

    Business hours:
    - Monday-Friday: 9 AM - 5 PM (excluding 12-1 PM lunch)
    - Saturday: 9 AM - 3 PM (excluding 12-1 PM lunch)
    - Sunday: Closed

    Args:
        date: Date string in YYYY-MM-DD format
        duration_minutes: Slot duration in minutes (default: 30)

    Returns:
        Dict with available slots:
            {
                "success": True,
                "date": str,
                "day_of_week": str,
                "available_slots": [str] (ISO timestamps),
                "message": str
            }

    Raises:
        ValueError: If date format is invalid

    Note:
        This is a POC mock implementation. Feature 7 will integrate with
        Google Calendar to check actual availability.
    """
    try:
        # Parse and validate date
        slot_date = datetime.fromisoformat(date).date()
        day_of_week = slot_date.strftime("%A")

        # Check if Sunday (closed)
        if slot_date.weekday() == 6:  # Sunday
            return {
                "success": True,
                "date": date,
                "day_of_week": day_of_week,
                "available_slots": [],
                "message": "We are closed on Sundays",
            }

        # Determine business hours
        if slot_date.weekday() < 5:  # Monday-Friday
            start_hour, end_hour = 9, 17  # 9 AM - 5 PM
        else:  # Saturday
            start_hour, end_hour = 9, 15  # 9 AM - 3 PM

        # Generate slots
        slots = []
        current_time = datetime.combine(slot_date, datetime.min.time()).replace(
            hour=start_hour, tzinfo=timezone.utc
        )
        end_time = datetime.combine(slot_date, datetime.min.time()).replace(
            hour=end_hour, tzinfo=timezone.utc
        )
        lunch_start = datetime.combine(slot_date, datetime.min.time()).replace(
            hour=12, tzinfo=timezone.utc
        )
        lunch_end = datetime.combine(slot_date, datetime.min.time()).replace(
            hour=13, tzinfo=timezone.utc
        )

        while current_time < end_time:
            # Skip lunch hour (12 PM - 1 PM)
            if not (lunch_start <= current_time < lunch_end):
                slots.append(current_time.isoformat())

            current_time += timedelta(minutes=duration_minutes)

        logger.info(f"Generated {len(slots)} available slots for {date}")

        return {
            "success": True,
            "date": date,
            "day_of_week": day_of_week,
            "available_slots": slots,
            "message": f"Found {len(slots)} available time slots",
        }

    except ValueError as e:
        logger.error(f"Invalid date format {date}: {e}")
        return {
            "success": False,
            "error": "Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-15)",
            "message": "Invalid date format",
        }
    except Exception as e:
        logger.error(f"Error generating slots for {date}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "message": "Error generating available slots"}


# ============================================================================
# Tool 3: Book Appointment
# ============================================================================


async def book_appointment(
    db: AsyncSession,
    customer_id: int,
    vehicle_id: int,
    scheduled_at: str,
    service_type: str,
    duration_minutes: int = 60,
    service_description: Optional[str] = None,
    customer_concerns: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Book a service appointment.

    Args:
        db: Database session
        customer_id: Customer ID
        vehicle_id: Vehicle ID
        scheduled_at: ISO format datetime string (e.g., "2025-01-15T09:00:00")
        service_type: Type of service (must be valid ServiceType enum)
        duration_minutes: Appointment duration in minutes (default: 60)
        service_description: Optional service description
        customer_concerns: Optional customer concerns
        notes: Optional notes

    Returns:
        Dict with appointment details:
            {
                "success": True,
                "data": {
                    "appointment_id": int,
                    "customer_id": int,
                    "customer_name": str,
                    "vehicle_id": int,
                    "vehicle_description": str,
                    "scheduled_at": str,
                    "service_type": str,
                    "duration_minutes": int,
                    "status": str
                },
                "message": str
            }

    Note:
        Feature 7 will create a Google Calendar event for this appointment.
    """
    try:
        # Validate customer exists
        customer = await db.get(Customer, customer_id)
        if not customer:
            logger.warning(f"Customer {customer_id} not found")
            return {
                "success": False,
                "error": f"Customer ID {customer_id} not found",
                "message": "Customer not found",
            }

        # Validate vehicle exists and belongs to customer
        vehicle = await db.get(Vehicle, vehicle_id)
        if not vehicle:
            logger.warning(f"Vehicle {vehicle_id} not found")
            return {
                "success": False,
                "error": f"Vehicle ID {vehicle_id} not found",
                "message": "Vehicle not found",
            }

        if vehicle.customer_id != customer_id:
            logger.warning(f"Vehicle {vehicle_id} does not belong to customer {customer_id}")
            return {
                "success": False,
                "error": f"Vehicle {vehicle_id} does not belong to customer {customer_id}",
                "message": "Vehicle does not belong to this customer",
            }

        # Parse scheduled datetime
        try:
            scheduled_datetime = datetime.fromisoformat(scheduled_at)
            # Remove timezone info since DB column is TIMESTAMP WITHOUT TIME ZONE
            if scheduled_datetime.tzinfo is not None:
                scheduled_datetime = scheduled_datetime.replace(tzinfo=None)
        except ValueError as e:
            logger.error(f"Invalid datetime format {scheduled_at}: {e}")
            return {
                "success": False,
                "error": "Invalid datetime format. Use ISO format (e.g., 2025-01-15T09:00:00)",
                "message": "Invalid datetime format",
            }

        # Validate service_type enum
        try:
            service_type_enum = ServiceType(service_type)
        except ValueError:
            valid_types = [t.value for t in ServiceType]
            logger.error(f"Invalid service_type {service_type}")
            return {
                "success": False,
                "error": f"Invalid service_type. Must be one of: {', '.join(valid_types)}",
                "message": "Invalid service type",
            }

        # Create appointment
        appointment = Appointment(
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            scheduled_at=scheduled_datetime,
            duration_minutes=duration_minutes,
            service_type=service_type_enum,
            service_description=service_description,
            customer_concerns=customer_concerns,
            notes=notes,
            status=AppointmentStatus.SCHEDULED,
            confirmation_sent=True,
            booking_method="ai_voice",
            booked_by="AI Voice Agent",
        )

        db.add(appointment)
        await db.commit()
        await db.refresh(appointment)

        logger.info(
            f"Appointment {appointment.id} created for customer {customer_id}, "
            f"vehicle {vehicle_id} at {scheduled_at}"
        )

        # Invalidate customer cache (data changed)
        await invalidate_customer_cache(customer.phone_number)

        # Build response
        customer_name = f"{customer.first_name} {customer.last_name}"
        vehicle_description = f"{vehicle.year} {vehicle.make} {vehicle.model}"

        return {
            "success": True,
            "data": {
                "appointment_id": appointment.id,
                "customer_id": customer_id,
                "customer_name": customer_name,
                "vehicle_id": vehicle_id,
                "vehicle_description": vehicle_description,
                "scheduled_at": scheduled_datetime.isoformat(),
                "service_type": service_type,
                "duration_minutes": duration_minutes,
                "status": appointment.status.value,
            },
            "message": f"Appointment booked successfully for {customer_name} on {scheduled_datetime.strftime('%B %d, %Y at %I:%M %p')}",
        }

    except Exception as e:
        logger.error(f"Error booking appointment: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "error": str(e), "message": "Error booking appointment"}


# ============================================================================
# Tool 4: Get Upcoming Appointments
# ============================================================================


async def get_upcoming_appointments(db: AsyncSession, customer_id: int) -> Dict[str, Any]:
    """
    Get upcoming appointments for a customer.

    Args:
        db: Database session
        customer_id: Customer ID

    Returns:
        Dict with appointments list:
            {
                "success": True,
                "data": {
                    "customer_id": int,
                    "appointments": [
                        {
                            "appointment_id": int,
                            "scheduled_at": str,
                            "service_type": str,
                            "duration_minutes": int,
                            "status": str,
                            "vehicle": {
                                "id": int,
                                "year": int,
                                "make": str,
                                "model": str,
                                "vin": str
                            },
                            "service_description": str | None,
                            "confirmation_sent": bool
                        }
                    ]
                },
                "message": str
            }
    """
    try:
        # Validate customer exists
        customer = await db.get(Customer, customer_id)
        if not customer:
            logger.warning(f"Customer {customer_id} not found")
            return {
                "success": False,
                "error": f"Customer ID {customer_id} not found",
                "message": "Customer not found",
            }

        # Query upcoming appointments
        now = datetime.now(timezone.utc)
        stmt = (
            select(Appointment)
            .options(selectinload(Appointment.vehicle))
            .where(
                Appointment.customer_id == customer_id,
                Appointment.scheduled_at > now,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
            )
            .order_by(Appointment.scheduled_at.asc())
        )

        result = await db.execute(stmt)
        appointments = result.scalars().all()

        # Build response
        appointments_data = []
        for appt in appointments:
            appointments_data.append(
                {
                    "appointment_id": appt.id,
                    "scheduled_at": appt.scheduled_at.isoformat(),
                    "service_type": appt.service_type.value,
                    "duration_minutes": appt.duration_minutes,
                    "status": appt.status.value,
                    "vehicle": {
                        "id": appt.vehicle.id,
                        "year": appt.vehicle.year,
                        "make": appt.vehicle.make,
                        "model": appt.vehicle.model,
                        "vin": appt.vehicle.vin,
                    },
                    "service_description": appt.service_description,
                    "confirmation_sent": appt.confirmation_sent,
                }
            )

        logger.info(
            f"Found {len(appointments_data)} upcoming appointments for customer {customer_id}"
        )

        return {
            "success": True,
            "data": {
                "customer_id": customer_id,
                "appointments": appointments_data,
            },
            "message": f"Found {len(appointments_data)} upcoming appointment{'s' if len(appointments_data) != 1 else ''}",
        }

    except Exception as e:
        logger.error(f"Error getting appointments for customer {customer_id}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "message": "Error retrieving appointments"}


# ============================================================================
# Tool 5: Cancel Appointment
# ============================================================================


async def cancel_appointment(db: AsyncSession, appointment_id: int, reason: str) -> Dict[str, Any]:
    """
    Cancel an appointment.

    Args:
        db: Database session
        appointment_id: Appointment ID to cancel
        reason: Cancellation reason

    Returns:
        Dict with cancellation result:
            {
                "success": True,
                "data": {
                    "appointment_id": int,
                    "status": str,
                    "cancellation_reason": str,
                    "cancelled_at": str
                },
                "message": str
            }

    Note:
        Feature 7 will delete the corresponding Google Calendar event.
    """
    try:
        # Get appointment
        appointment = await db.get(Appointment, appointment_id)
        if not appointment:
            logger.warning(f"Appointment {appointment_id} not found")
            return {
                "success": False,
                "error": f"Appointment ID {appointment_id} not found",
                "message": "Appointment not found",
            }

        # Check if already cancelled
        if appointment.status == AppointmentStatus.CANCELLED:
            logger.info(f"Appointment {appointment_id} already cancelled")
            return {
                "success": False,
                "error": "Appointment is already cancelled",
                "message": "Appointment is already cancelled",
            }

        # Update appointment
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancellation_reason = reason
        cancelled_at = datetime.now(timezone.utc)
        # Note: cancelled_at column doesn't exist in schema, using updated_at

        await db.commit()
        await db.refresh(appointment)

        logger.info(f"Appointment {appointment_id} cancelled. Reason: {reason}")

        # Invalidate customer cache
        customer = await db.get(Customer, appointment.customer_id)
        if customer:
            await invalidate_customer_cache(customer.phone_number)

        return {
            "success": True,
            "data": {
                "appointment_id": appointment_id,
                "status": appointment.status.value,
                "cancellation_reason": reason,
                "cancelled_at": cancelled_at.isoformat(),
            },
            "message": f"Appointment cancelled successfully. Reason: {reason}",
        }

    except Exception as e:
        logger.error(f"Error cancelling appointment {appointment_id}: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "error": str(e), "message": "Error cancelling appointment"}


# ============================================================================
# Tool 6: Reschedule Appointment
# ============================================================================


async def reschedule_appointment(
    db: AsyncSession, appointment_id: int, new_datetime: str
) -> Dict[str, Any]:
    """
    Reschedule an appointment to a new time.

    Args:
        db: Database session
        appointment_id: Appointment ID to reschedule
        new_datetime: New datetime in ISO format (e.g., "2025-01-16T14:00:00")

    Returns:
        Dict with reschedule result:
            {
                "success": True,
                "data": {
                    "appointment_id": int,
                    "old_datetime": str,
                    "new_datetime": str,
                    "service_type": str,
                    "status": str
                },
                "message": str
            }

    Note:
        Feature 7 will update the corresponding Google Calendar event.
    """
    try:
        # Get appointment
        appointment = await db.get(Appointment, appointment_id)
        if not appointment:
            logger.warning(f"Appointment {appointment_id} not found")
            return {
                "success": False,
                "error": f"Appointment ID {appointment_id} not found",
                "message": "Appointment not found",
            }

        # Check if cancelled
        if appointment.status == AppointmentStatus.CANCELLED:
            logger.warning(f"Cannot reschedule cancelled appointment {appointment_id}")
            return {
                "success": False,
                "error": "Cannot reschedule a cancelled appointment",
                "message": "Cannot reschedule cancelled appointment",
            }

        # Parse new datetime
        try:
            new_scheduled_at = datetime.fromisoformat(new_datetime)
            # Remove timezone info since DB column is TIMESTAMP WITHOUT TIME ZONE
            if new_scheduled_at.tzinfo is not None:
                new_scheduled_at = new_scheduled_at.replace(tzinfo=None)
        except ValueError as e:
            logger.error(f"Invalid datetime format {new_datetime}: {e}")
            return {
                "success": False,
                "error": "Invalid datetime format. Use ISO format (e.g., 2025-01-16T14:00:00)",
                "message": "Invalid datetime format",
            }

        # Store old datetime for response
        old_datetime = appointment.scheduled_at.isoformat()

        # Update appointment
        appointment.scheduled_at = new_scheduled_at

        await db.commit()
        await db.refresh(appointment)

        logger.info(
            f"Appointment {appointment_id} rescheduled from {old_datetime} to {new_datetime}"
        )

        # Invalidate customer cache
        customer = await db.get(Customer, appointment.customer_id)
        if customer:
            await invalidate_customer_cache(customer.phone_number)

        return {
            "success": True,
            "data": {
                "appointment_id": appointment_id,
                "old_datetime": old_datetime,
                "new_datetime": new_scheduled_at.isoformat(),
                "service_type": appointment.service_type.value,
                "status": appointment.status.value,
            },
            "message": f"Appointment rescheduled successfully to {new_scheduled_at.strftime('%B %d, %Y at %I:%M %p')}",
        }

    except Exception as e:
        logger.error(f"Error rescheduling appointment {appointment_id}: {e}", exc_info=True)
        await db.rollback()
        return {"success": False, "error": str(e), "message": "Error rescheduling appointment"}


# ============================================================================
# Tool 7: Decode VIN
# ============================================================================


async def decode_vin(vin: str) -> Dict[str, Any]:
    """
    Decode a VIN using the NHTSA API with caching.

    Args:
        vin: 17-character VIN

    Returns:
        Dict with vehicle information:
            {
                "success": True,
                "data": {
                    "vin": str,
                    "make": str,
                    "model": str,
                    "year": int,
                    "vehicle_type": str,
                    "manufacturer": str
                },
                "message": str
            }

    Note:
        Results are cached for 7 days since VIN data doesn't change.
        HTTP timeout is 5 seconds.
    """
    try:
        # Validate VIN format
        vin_upper = vin.upper().strip()

        if len(vin_upper) != 17:
            logger.warning(f"Invalid VIN length: {len(vin_upper)}")
            return {
                "success": False,
                "error": f"VIN must be exactly 17 characters, got {len(vin_upper)}",
                "message": "Invalid VIN length",
            }

        # VIN regex - alphanumeric excluding I, O, Q
        vin_pattern = r"^[A-HJ-NPR-Z0-9]{17}$"
        if not re.match(vin_pattern, vin_upper):
            logger.warning(f"Invalid VIN format: {vin_upper}")
            return {
                "success": False,
                "error": "Invalid VIN format. VIN must contain only letters (except I, O, Q) and numbers",
                "message": "Invalid VIN format",
            }

        # Check cache first
        redis_client = get_redis()
        cache_key = f"{VIN_CACHE_PREFIX}{vin_upper}"

        if redis_client:
            try:
                cached_result = await asyncio.wait_for(redis_client.get(cache_key), timeout=2.0)
                if cached_result:
                    import json

                    logger.info(f"VIN cache hit: {vin_upper}")
                    return json.loads(cached_result)
            except asyncio.TimeoutError:
                logger.warning(f"Redis timeout checking VIN cache for {vin_upper}")
            except Exception as e:
                logger.warning(f"Redis error checking VIN cache: {e}")

        # Cache miss - call NHTSA API
        logger.info(f"VIN cache miss: {vin_upper}, calling NHTSA API")

        url = f"{NHTSA_API_BASE}/DecodeVin/{vin_upper}?format=json"

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        # Parse NHTSA response
        # Response format: {"Results": [{"Variable": "Make", "Value": "HONDA"}, ...]}
        results = data.get("Results", [])

        # Build lookup dict
        vin_data = {}
        for item in results:
            variable = item.get("Variable", "")
            value = item.get("Value", "")
            if value and value.strip():  # Only include non-empty values
                vin_data[variable] = value

        # Extract key fields
        make = vin_data.get("Make", "Unknown")
        model = vin_data.get("Model", "Unknown")
        year_str = vin_data.get("Model Year", "")
        vehicle_type = vin_data.get("Vehicle Type", "Unknown")
        manufacturer = vin_data.get("Manufacturer Name", "Unknown")

        # Parse year
        try:
            year = int(year_str) if year_str else None
        except ValueError:
            year = None

        # Check if VIN was valid (NHTSA returns error codes)
        error_code = vin_data.get("Error Code", "0")
        if error_code != "0" and error_code != 0:
            error_text = vin_data.get("Error Text", "Unknown error")
            logger.warning(f"NHTSA API error for VIN {vin_upper}: {error_text}")
            return {
                "success": False,
                "error": f"Invalid VIN or unable to decode: {error_text}",
                "message": "Invalid VIN",
            }

        # Build response
        result = {
            "success": True,
            "data": {
                "vin": vin_upper,
                "make": make,
                "model": model,
                "year": year,
                "vehicle_type": vehicle_type,
                "manufacturer": manufacturer,
            },
            "message": f"VIN decoded successfully: {year} {make} {model}",
        }

        # Cache successful result (7 days)
        if redis_client:
            try:
                import json

                await asyncio.wait_for(
                    redis_client.setex(cache_key, VIN_CACHE_TTL, json.dumps(result)), timeout=2.0
                )
                logger.info(f"VIN cached: {vin_upper}")
            except asyncio.TimeoutError:
                logger.warning(f"Redis timeout caching VIN {vin_upper}")
            except Exception as e:
                logger.warning(f"Redis error caching VIN: {e}")

        return result

    except httpx.TimeoutException:
        logger.error(f"NHTSA API timeout for VIN {vin}")
        return {
            "success": False,
            "error": "NHTSA API request timed out",
            "message": "VIN decode service timeout",
        }
    except httpx.HTTPStatusError as e:
        logger.error(f"NHTSA API HTTP error for VIN {vin}: {e}")
        return {
            "success": False,
            "error": f"NHTSA API error: {e.response.status_code}",
            "message": "VIN decode service error",
        }
    except Exception as e:
        logger.error(f"Error decoding VIN {vin}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "message": "Error decoding VIN"}
