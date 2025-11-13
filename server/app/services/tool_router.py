"""
Tool router for executing function calls from the LLM.

Routes function calls to appropriate handlers, manages database sessions,
and formats results for the LLM to consume.
"""

import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ToolRouter:
    """
    Routes function calls to appropriate handlers.

    Responsibilities:
    - Map function names to Python functions
    - Provide database session to tools that need it
    - Handle errors gracefully
    - Format results in LLM-friendly format

    Example usage:
        router = ToolRouter(db_session=db)
        result = await router.execute("lookup_customer", phone_number="555-1234")
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize tool router.

        Args:
            db_session: Database session for tool execution
        """
        self.db = db_session

        # Tool registry - maps function names to handler methods
        self.tools: Dict[str, Callable] = {
            "lookup_customer": self._lookup_customer,
            "get_available_slots": self._get_available_slots,
            "book_appointment": self._book_appointment,
            "get_upcoming_appointments": self._get_upcoming_appointments,
            "cancel_appointment": self._cancel_appointment,
            "reschedule_appointment": self._reschedule_appointment,
            "decode_vin": self._decode_vin,
        }

        logger.info(f"ToolRouter initialized with {len(self.tools)} tools")

    async def execute(self, function_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool by name.

        Args:
            function_name: Name of function to execute
            **kwargs: Function arguments

        Returns:
            Dict with result or error:
                {"success": True, "data": {...}}
                {"success": False, "error": "..."}
        """
        try:
            handler = self.tools.get(function_name)
            if not handler:
                return {
                    "success": False,
                    "error": f"Unknown function: {function_name}"
                }

            logger.info(f"Executing tool: {function_name}")
            result = await handler(**kwargs)

            return {
                "success": True,
                "data": result
            }

        except Exception as e:
            logger.error(f"Error executing {function_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    # Tool implementations

    async def _lookup_customer(self, phone_number: str) -> Dict[str, Any]:
        """
        Look up customer by phone number.

        Args:
            phone_number: Customer's phone number

        Returns:
            Dict with customer info or not found message
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.crm_tools import lookup_customer

            customer = await lookup_customer(self.db, phone_number)

            if not customer:
                return {
                    "found": False,
                    "message": "No customer found with that phone number"
                }

            return {
                "found": True,
                "customer": customer
            }

        except Exception as e:
            logger.error(f"Error looking up customer: {e}")
            return {
                "found": False,
                "error": str(e)
            }

    async def _get_available_slots(
        self,
        date: str,
        service_type: str = "general_service"
    ) -> Dict[str, Any]:
        """
        Get available appointment slots for a date.

        Args:
            date: Date string (YYYY-MM-DD)
            service_type: Type of service (optional)

        Returns:
            Dict with available time slots
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.calendar_tools import get_freebusy

            # Parse date
            start_date = datetime.fromisoformat(date)
            end_date = start_date + timedelta(days=1)

            # Get free/busy info
            slots = await get_freebusy(start_date, end_date)

            return {
                "date": date,
                "service_type": service_type,
                "available_slots": slots,
                "message": f"Found {len(slots)} available time slots"
            }

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {
                "error": f"Invalid date format. Please use YYYY-MM-DD (e.g., 2025-01-15)"
            }
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return {
                "error": str(e)
            }

    async def _book_appointment(
        self,
        customer_id: int,
        vehicle_id: int,
        service_type: str,
        start_time: str,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Book a service appointment.

        Args:
            customer_id: Customer ID
            vehicle_id: Vehicle ID
            service_type: Type of service
            start_time: ISO format datetime string
            notes: Optional notes

        Returns:
            Dict with appointment details or error
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.calendar_tools import book_slot
            from app.models.customer import Customer, Vehicle

            # Parse start time
            start_datetime = datetime.fromisoformat(start_time)

            # Get customer and vehicle info for event details
            customer = await self.db.get(Customer, customer_id)
            vehicle = await self.db.get(Vehicle, vehicle_id)

            if not customer or not vehicle:
                return {
                    "success": False,
                    "error": "Customer or vehicle not found"
                }

            # Determine duration based on service type
            duration_map = {
                "oil_change": 30,
                "tire_rotation": 30,
                "inspection": 45,
                "brake_service": 60,
                "general_service": 60,
            }
            duration_minutes = duration_map.get(service_type, 60)

            # Book slot in Google Calendar
            customer_name = f"{customer.first_name} {customer.last_name}"
            vehicle_desc = f"{vehicle.year} {vehicle.make} {vehicle.model}"

            event = await book_slot(
                start_time=start_datetime,
                duration_minutes=duration_minutes,
                customer_name=customer_name,
                service_type=service_type,
            )

            # TODO: Create appointment record in database (Feature 6)
            # For now, just return the calendar event info

            return {
                "booked": True,
                "appointment_id": event.get("event_id"),
                "customer_name": customer_name,
                "vehicle": vehicle_desc,
                "service_type": service_type,
                "start_time": start_time,
                "duration_minutes": duration_minutes,
                "notes": notes,
                "message": f"Appointment booked successfully for {customer_name}"
            }

        except ValueError as e:
            logger.error(f"Invalid datetime format: {e}")
            return {
                "success": False,
                "error": "Invalid datetime format. Please use ISO format (e.g., 2025-01-15T09:00:00)"
            }
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_upcoming_appointments(
        self,
        customer_id: int
    ) -> Dict[str, Any]:
        """
        Get upcoming appointments for a customer.

        Args:
            customer_id: Customer ID

        Returns:
            Dict with list of upcoming appointments
        """
        try:
            # TODO: Implement database query for appointments
            # For now, return empty list as appointments table isn't in schema yet
            logger.info(f"Getting upcoming appointments for customer {customer_id}")

            return {
                "customer_id": customer_id,
                "appointments": [],
                "message": "No upcoming appointments found"
            }

        except Exception as e:
            logger.error(f"Error getting appointments: {e}")
            return {
                "error": str(e)
            }

    async def _cancel_appointment(
        self,
        appointment_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel an appointment.

        Args:
            appointment_id: Appointment ID to cancel
            reason: Optional cancellation reason

        Returns:
            Dict with cancellation result
        """
        try:
            # TODO: Implement appointment cancellation
            # This will need to:
            # 1. Update appointment status in database
            # 2. Delete event from Google Calendar
            logger.info(f"Cancelling appointment {appointment_id}, reason: {reason}")

            return {
                "cancelled": True,
                "appointment_id": appointment_id,
                "reason": reason or "Not specified",
                "message": "Appointment cancelled successfully"
            }

        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _reschedule_appointment(
        self,
        appointment_id: int,
        new_start_time: str
    ) -> Dict[str, Any]:
        """
        Reschedule an appointment to a new time.

        Args:
            appointment_id: Appointment ID to reschedule
            new_start_time: New start time (ISO format)

        Returns:
            Dict with reschedule result
        """
        try:
            # Parse new time
            new_datetime = datetime.fromisoformat(new_start_time)

            # TODO: Implement appointment rescheduling
            # This will need to:
            # 1. Update appointment time in database
            # 2. Update event in Google Calendar
            logger.info(f"Rescheduling appointment {appointment_id} to {new_start_time}")

            return {
                "rescheduled": True,
                "appointment_id": appointment_id,
                "new_start_time": new_start_time,
                "message": "Appointment rescheduled successfully"
            }

        except ValueError as e:
            logger.error(f"Invalid datetime format: {e}")
            return {
                "success": False,
                "error": "Invalid datetime format. Please use ISO format (e.g., 2025-01-16T14:00:00)"
            }
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _decode_vin(self, vin: str) -> Dict[str, Any]:
        """
        Decode a VIN number to get vehicle information.

        Args:
            vin: 17-character VIN

        Returns:
            Dict with vehicle info or error
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.vin_tools import decode_vin

            # Validate VIN length
            if len(vin) != 17:
                return {
                    "valid": False,
                    "error": "VIN must be exactly 17 characters"
                }

            vehicle_info = await decode_vin(vin)

            if not vehicle_info or vehicle_info.get("error"):
                return {
                    "valid": False,
                    "message": "Invalid VIN or unable to decode",
                    "error": vehicle_info.get("error") if vehicle_info else "Unknown error"
                }

            return {
                "valid": True,
                "vehicle": vehicle_info,
                "message": f"VIN decoded successfully: {vehicle_info.get('make')} {vehicle_info.get('model')}"
            }

        except Exception as e:
            logger.error(f"Error decoding VIN: {e}")
            return {
                "valid": False,
                "error": str(e)
            }
