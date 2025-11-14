"""
Tool router for executing function calls from the LLM.

Routes function calls to appropriate handlers, manages database sessions,
and formats results for the LLM to consume.
"""

import logging
from typing import Any, Callable, Dict

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
                {
                    "success": True/False,
                    "data": {...},
                    "message": "Human-readable message",
                    "error": "Error details if failed"
                }
        """
        try:
            handler = self.tools.get(function_name)
            if not handler:
                logger.warning(f"Unknown function requested: {function_name}")
                return {
                    "success": False,
                    "error": f"Unknown function: {function_name}",
                    "message": f"Function '{function_name}' is not available",
                }

            logger.info(f"Executing tool: {function_name} with args: {list(kwargs.keys())}")
            result = await handler(**kwargs)

            # Tool functions return their own success/error structure
            return result

        except Exception as e:
            logger.error(f"Error executing {function_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Unexpected error executing {function_name}",
            }

    # ========================================================================
    # Tool Implementations
    # ========================================================================

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
                    "success": True,
                    "data": {"found": False},
                    "message": "No customer found with that phone number",
                }

            return {
                "success": True,
                "data": {"found": True, "customer": customer},
                "message": f"Customer found: {customer.get('first_name')} {customer.get('last_name')}",
            }

        except Exception as e:
            logger.error(f"Error looking up customer: {e}", exc_info=True)
            return {"success": False, "error": str(e), "message": "Error looking up customer"}

    async def _get_available_slots(self, date: str, service_type: str = None) -> Dict[str, Any]:
        """
        Get available appointment slots for a date.

        Args:
            date: Date string (YYYY-MM-DD)
            service_type: Type of service (optional) - maps to duration

        Returns:
            Dict with available time slots
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.crm_tools import get_available_slots

            # Map service type to duration (if provided)
            service_duration_map = {
                "oil_change": 30,
                "tire_rotation": 30,
                "inspection": 45,
                "brake_service": 90,
                "general_service": 60,
            }
            duration_minutes = service_duration_map.get(service_type, 60) if service_type else 60

            result = await get_available_slots(date, duration_minutes)

            # get_available_slots returns its own success/error structure
            return result

        except Exception as e:
            logger.error(f"Error getting available slots: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Error retrieving available slots",
            }

    async def _book_appointment(
        self,
        customer_id: int,
        vehicle_id: int,
        service_type: str,
        start_time: str,
        notes: str = None,
    ) -> Dict[str, Any]:
        """
        Book a service appointment.

        Args:
            customer_id: Customer ID
            vehicle_id: Vehicle ID
            service_type: Type of service
            start_time: ISO format datetime string (matches schema parameter name)
            notes: Optional notes

        Returns:
            Dict with appointment details or error
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.crm_tools import book_appointment

            # Map service type to duration
            service_duration_map = {
                "oil_change": 30,
                "tire_rotation": 30,
                "inspection": 45,
                "brake_service": 90,
                "general_service": 60,
            }
            duration_minutes = service_duration_map.get(service_type, 60)

            result = await book_appointment(
                db=self.db,
                customer_id=customer_id,
                vehicle_id=vehicle_id,
                scheduled_at=start_time,  # Map start_time to scheduled_at for crm_tools
                service_type=service_type,
                duration_minutes=duration_minutes,
                service_description=None,
                customer_concerns=notes,  # Map notes to customer_concerns
                notes=notes,
            )

            # book_appointment returns its own success/error structure
            return result

        except Exception as e:
            logger.error(f"Error booking appointment: {e}", exc_info=True)
            return {"success": False, "error": str(e), "message": "Error booking appointment"}

    async def _get_upcoming_appointments(self, customer_id: int) -> Dict[str, Any]:
        """
        Get upcoming appointments for a customer.

        Args:
            customer_id: Customer ID

        Returns:
            Dict with list of upcoming appointments
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.crm_tools import get_upcoming_appointments

            result = await get_upcoming_appointments(self.db, customer_id)

            # get_upcoming_appointments returns its own success/error structure
            return result

        except Exception as e:
            logger.error(f"Error getting appointments: {e}", exc_info=True)
            return {"success": False, "error": str(e), "message": "Error retrieving appointments"}

    async def _cancel_appointment(
        self, appointment_id: int, reason: str = "Not specified"
    ) -> Dict[str, Any]:
        """
        Cancel an appointment.

        Args:
            appointment_id: Appointment ID to cancel
            reason: Cancellation reason (default: "Not specified")

        Returns:
            Dict with cancellation result
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.crm_tools import cancel_appointment

            result = await cancel_appointment(self.db, appointment_id, reason)

            # cancel_appointment returns its own success/error structure
            return result

        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}", exc_info=True)
            return {"success": False, "error": str(e), "message": "Error cancelling appointment"}

    async def _reschedule_appointment(
        self, appointment_id: int, new_start_time: str
    ) -> Dict[str, Any]:
        """
        Reschedule an appointment to a new time.

        Args:
            appointment_id: Appointment ID to reschedule
            new_start_time: New datetime (ISO format) - matches schema parameter name

        Returns:
            Dict with reschedule result
        """
        try:
            # Import here to avoid circular dependencies
            from app.tools.crm_tools import reschedule_appointment

            result = await reschedule_appointment(self.db, appointment_id, new_start_time)

            # reschedule_appointment returns its own success/error structure
            return result

        except Exception as e:
            logger.error(f"Error rescheduling appointment: {e}", exc_info=True)
            return {"success": False, "error": str(e), "message": "Error rescheduling appointment"}

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
            from app.tools.crm_tools import decode_vin

            result = await decode_vin(vin)

            # decode_vin returns its own success/error structure
            return result

        except Exception as e:
            logger.error(f"Error decoding VIN: {e}", exc_info=True)
            return {"success": False, "error": str(e), "message": "Error decoding VIN"}
