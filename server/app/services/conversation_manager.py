"""
Conversation Flow State Machine for Automotive Voice Agent.

Manages conversation states and orchestrates flow logic for 6 distinct call scenarios:
1. New Customer - First Appointment
2. Existing Customer - Service Appointment
3. Appointment Modification (Reschedule/Cancel)
4. General Inquiry
5. Appointment Reminder (Outbound)
6. Post-Service Follow-Up (Outbound)
"""

import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.services.system_prompts import build_system_prompt

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """
    Conversation state machine states.

    Flow progression (typical):
        GREETING → VERIFICATION → INTENT_DETECTION → SLOT_COLLECTION
        → CONFIRMATION → EXECUTION → CLOSING

    Special states:
        ESCALATION: Transfer to human
    """

    GREETING = "greeting"
    VERIFICATION = "verification"
    INTENT_DETECTION = "intent_detection"
    SLOT_COLLECTION = "slot_collection"
    CONFIRMATION = "confirmation"
    EXECUTION = "execution"
    CLOSING = "closing"
    ESCALATION = "escalation"


class CallType(Enum):
    """Types of calls the system can handle."""

    INBOUND_NEW = "inbound_new"  # New customer calling
    INBOUND_EXISTING = "inbound_existing"  # Existing customer calling
    INBOUND_GENERAL = "inbound_general"  # General inquiry
    OUTBOUND_REMINDER = "outbound_reminder"  # Reminder call
    OUTBOUND_FOLLOWUP = "outbound_followup"  # Post-service follow-up


class Intent(Enum):
    """Detected user intents."""

    SCHEDULE_APPOINTMENT = "schedule_appointment"
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    GENERAL_INQUIRY = "general_inquiry"
    CHECK_HOURS = "check_hours"
    CHECK_PRICING = "check_pricing"
    CHECK_SERVICES = "check_services"
    COMPLAINT = "complaint"
    CONFIRM_REMINDER = "confirm_reminder"
    UNKNOWN = "unknown"


class ConversationManager:
    """
    Manages conversation flow and state transitions.

    Architecture:
        - State machine: Tracks conversation progress
        - Slot collection: Gathers required information
        - Intent detection: Identifies customer needs
        - Escalation detection: Triggers human handoff
        - Dynamic prompts: Updates system prompt based on context

    Usage:
        # Initialize for call
        manager = ConversationManager(
            call_type=CallType.INBOUND_NEW,
            caller_phone="+15551234567"
        )

        # Get initial system prompt
        prompt = manager.get_system_prompt()

        # Update state as conversation progresses
        manager.process_message(user_message, assistant_response)

        # Check if escalation needed
        if manager.should_escalate():
            # Transfer to human
            pass
    """

    def __init__(
        self,
        call_type: CallType,
        caller_phone: Optional[str] = None,
        customer_data: Optional[Dict[str, Any]] = None,
        appointment_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize conversation manager.

        Args:
            call_type: Type of call (inbound/outbound)
            caller_phone: Caller phone number
            customer_data: Customer information (if existing customer)
            appointment_data: Appointment details (if outbound call)
        """
        self.call_type = call_type
        self.caller_phone = caller_phone
        self.customer_data = customer_data or {}
        self.appointment_data = appointment_data or {}

        # State machine
        self.state = ConversationState.GREETING
        self.intent: Optional[Intent] = None

        # Slot collection
        self.collected_slots: Dict[str, Any] = {}
        self.required_slots: List[str] = []

        # Conversation tracking
        self.turn_count = 0
        self.escalation_triggered = False
        self.escalation_reason: Optional[str] = None

        logger.info(
            f"ConversationManager initialized: call_type={call_type.value}, "
            f"customer={'known' if customer_data else 'unknown'}"
        )

    def get_system_prompt(self) -> str:
        """
        Generate appropriate system prompt based on call type and state.

        Returns:
            System prompt string with context
        """
        # Map call type to prompt type
        prompt_type_map = {
            CallType.INBOUND_NEW: "inbound_new",
            CallType.INBOUND_EXISTING: "inbound_existing",
            CallType.INBOUND_GENERAL: "inbound_general",
            CallType.OUTBOUND_REMINDER: "outbound_reminder",
            CallType.OUTBOUND_FOLLOWUP: "outbound_reminder",  # Reuse reminder prompt
        }

        prompt_type = prompt_type_map.get(self.call_type, "inbound_general")

        # Build context for existing customers
        customer_context = None
        if self.call_type == CallType.INBOUND_EXISTING and self.customer_data:
            customer_context = self._build_customer_context()

        # Build context for outbound calls
        appointment_context = None
        if self.call_type in [CallType.OUTBOUND_REMINDER, CallType.OUTBOUND_FOLLOWUP]:
            appointment_context = self._build_appointment_context()

        # Generate base prompt
        prompt = build_system_prompt(
            call_type=prompt_type,
            customer_context=customer_context,
            appointment_context=appointment_context,
        )

        # Add state-specific guidance
        state_guidance = self._get_state_guidance()
        if state_guidance:
            prompt += f"\n\n### Current State Guidance\n{state_guidance}"

        # Add collected slots info
        if self.collected_slots:
            slots_str = "\n".join([f"- {k}: {v}" for k, v in self.collected_slots.items()])
            prompt += f"\n\n### Information Already Collected\n{slots_str}"

        return prompt

    def _build_customer_context(self) -> Dict[str, Any]:
        """Build customer context for prompt."""
        name = f"{self.customer_data.get('first_name', '')} {self.customer_data.get('last_name', '')}".strip()

        vehicles = self.customer_data.get("vehicles", [])
        vehicle_descriptions = [f"{v['year']} {v['make']} {v['model']}" for v in vehicles]

        return {
            "name": name or "this customer",
            "customer_since": self.customer_data.get("customer_since", "Unknown"),
            "last_service": self.customer_data.get("last_service_type", "No previous service"),
            "last_service_date": self.customer_data.get("last_service_date", ""),
            "vehicles": (
                ", ".join(vehicle_descriptions) if vehicle_descriptions else "No vehicles listed"
            ),
            "upcoming_appointments": self.customer_data.get("upcoming_appointments", "None"),
        }

    def _build_appointment_context(self) -> Dict[str, Any]:
        """Build appointment context for outbound calls."""
        return {
            "customer_name": self.appointment_data.get("customer_name", "the customer"),
            "service_type": self.appointment_data.get("service_type", "service"),
            "appointment_time": self.appointment_data.get(
                "appointment_time", "your scheduled time"
            ),
            "vehicle": self.appointment_data.get("vehicle", "your vehicle"),
        }

    def _get_state_guidance(self) -> Optional[str]:
        """Get guidance text for current state."""
        guidance_map = {
            ConversationState.GREETING: (
                "You are in the GREETING phase. Welcome the customer and identify their needs."
            ),
            ConversationState.VERIFICATION: (
                "You are in the VERIFICATION phase. Ask for one piece of identifying information:\n"
                "- Date of birth\n"
                "- Last 4 digits of phone number\n"
                "- Address\n"
                "- Vehicle VIN or license plate"
            ),
            ConversationState.INTENT_DETECTION: (
                "You are in the INTENT_DETECTION phase. Determine what the customer needs:\n"
                "- Schedule new appointment?\n"
                "- Reschedule existing appointment?\n"
                "- Cancel appointment?\n"
                "- General question?"
            ),
            ConversationState.SLOT_COLLECTION: (
                f"You are in the SLOT_COLLECTION phase. Collect required information.\n"
                f"Still needed: {', '.join(self.required_slots)}"
                if self.required_slots
                else "You are in the SLOT_COLLECTION phase. Collect required information."
            ),
            ConversationState.CONFIRMATION: (
                "You are in the CONFIRMATION phase. Repeat back all details and ask for confirmation."
            ),
            ConversationState.EXECUTION: (
                "You are in the EXECUTION phase. Use tools to complete the request."
            ),
            ConversationState.CLOSING: (
                "You are in the CLOSING phase. Thank the customer and ask if they need anything else."
            ),
            ConversationState.ESCALATION: (
                "ESCALATION triggered. Inform customer you're transferring to a service advisor."
            ),
        }

        return guidance_map.get(self.state)

    def process_message(
        self, user_message: str, assistant_response: Optional[str] = None
    ) -> ConversationState:
        """
        Process a conversation turn and update state.

        Args:
            user_message: User's message text
            assistant_response: Assistant's response text (optional)

        Returns:
            New conversation state
        """
        self.turn_count += 1

        # Check for escalation triggers
        if self.should_escalate(user_message):
            self.escalation_triggered = True
            self.state = ConversationState.ESCALATION
            logger.warning(f"Escalation triggered: {self.escalation_reason}")
            return self.state

        # Detect intent if not already detected
        if not self.intent and self.state in [
            ConversationState.GREETING,
            ConversationState.INTENT_DETECTION,
        ]:
            self.intent = self._detect_intent(user_message)
            logger.info(f"Intent detected: {self.intent.value}")

        # State transition logic
        old_state = self.state
        self.state = self._determine_next_state(user_message, assistant_response)

        if old_state != self.state:
            logger.info(f"State transition: {old_state.value} → {self.state.value}")

        return self.state

    def _detect_intent(self, message: str) -> Intent:
        """
        Detect user intent from message.

        Args:
            message: User message text

        Returns:
            Detected Intent
        """
        message_lower = message.lower()

        # Intent patterns
        intent_patterns = {
            Intent.SCHEDULE_APPOINTMENT: [
                r"\b(schedule|book|make|set up|get)\b.*\b(appointment|service)\b",
                r"\bneed\b.*\b(oil change|service|inspection|brakes)\b",
                r"\bwhen can (you|i)\b",
            ],
            Intent.RESCHEDULE_APPOINTMENT: [
                r"\b(reschedule|move|change|shift)\b.*\b(appointment|time)\b",
                r"\bneed to\b.*\b(reschedule|move)\b",
            ],
            Intent.CANCEL_APPOINTMENT: [
                r"\b(cancel|cancellation)\b",
                r"\bcan\'t make it\b",
                r"\bneed to cancel\b",
            ],
            Intent.CHECK_HOURS: [
                r"\b(hours|open|close|when.*open)\b",
                r"\bwhat time\b.*\b(open|close)\b",
            ],
            Intent.CHECK_PRICING: [
                r"\b(price|cost|how much|pricing)\b",
                r"\bhow much\b.*\b(oil change|service)\b",
            ],
            Intent.CHECK_SERVICES: [
                r"\bdo you\b.*\b(do|offer|have|provide)\b",
                r"\bwhat.*services\b",
            ],
            Intent.COMPLAINT: [
                r"\b(complaint|unhappy|dissatisfied|problem|issue)\b",
                r"\bnot happy\b",
                r"\blast (service|time)\b.*\b(problem|issue|bad)\b",
            ],
        }

        # Check patterns
        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return intent

        # Default to general inquiry if outbound reminder response
        if self.call_type == CallType.OUTBOUND_REMINDER:
            if any(word in message_lower for word in ["yes", "confirm", "correct", "right"]):
                return Intent.CONFIRM_REMINDER

        return Intent.GENERAL_INQUIRY

    def _determine_next_state(
        self, user_message: str, assistant_response: Optional[str]
    ) -> ConversationState:
        """
        Determine next state based on current state and messages.

        State machine transitions:

        GREETING → VERIFICATION (if existing customer) or INTENT_DETECTION (if new)
        VERIFICATION → INTENT_DETECTION
        INTENT_DETECTION → SLOT_COLLECTION or EXECUTION
        SLOT_COLLECTION → CONFIRMATION (when all slots filled)
        CONFIRMATION → EXECUTION (if confirmed) or SLOT_COLLECTION (if rejected)
        EXECUTION → CLOSING
        CLOSING → GREETING (if more questions) or END
        """
        # Current state
        current = self.state

        # GREETING state
        if current == ConversationState.GREETING:
            # For existing customers with sensitive operations, verify
            if self.call_type == CallType.INBOUND_EXISTING and self.intent in [
                Intent.RESCHEDULE_APPOINTMENT,
                Intent.CANCEL_APPOINTMENT,
            ]:
                return ConversationState.VERIFICATION
            # Otherwise move to intent detection
            return ConversationState.INTENT_DETECTION

        # VERIFICATION state
        elif current == ConversationState.VERIFICATION:
            # After verification, detect intent
            return ConversationState.INTENT_DETECTION

        # INTENT_DETECTION state
        elif current == ConversationState.INTENT_DETECTION:
            # For general inquiries, can go straight to execution
            if self.intent in [Intent.CHECK_HOURS, Intent.CHECK_PRICING, Intent.CHECK_SERVICES]:
                return ConversationState.EXECUTION

            # For appointment operations, collect slots
            if self.intent in [
                Intent.SCHEDULE_APPOINTMENT,
                Intent.RESCHEDULE_APPOINTMENT,
                Intent.CANCEL_APPOINTMENT,
            ]:
                self._set_required_slots()
                return ConversationState.SLOT_COLLECTION

            # Default to slot collection
            return ConversationState.SLOT_COLLECTION

        # SLOT_COLLECTION state
        elif current == ConversationState.SLOT_COLLECTION:
            # Update collected slots from message
            self._extract_slots(user_message)

            # Check if all required slots collected
            if self._all_slots_collected():
                return ConversationState.CONFIRMATION

            # Stay in slot collection
            return ConversationState.SLOT_COLLECTION

        # CONFIRMATION state
        elif current == ConversationState.CONFIRMATION:
            # Check for confirmation keywords
            message_lower = user_message.lower()
            confirmed = any(
                word in message_lower
                for word in ["yes", "correct", "right", "sounds good", "perfect", "confirm"]
            )
            rejected = any(
                word in message_lower for word in ["no", "wrong", "incorrect", "wait", "actually"]
            )

            if confirmed:
                return ConversationState.EXECUTION
            elif rejected:
                # Go back to slot collection to fix
                return ConversationState.SLOT_COLLECTION

            # Stay in confirmation
            return ConversationState.CONFIRMATION

        # EXECUTION state
        elif current == ConversationState.EXECUTION:
            # After execution, close conversation
            return ConversationState.CLOSING

        # CLOSING state
        elif current == ConversationState.CLOSING:
            # Check if customer has more questions
            message_lower = user_message.lower()
            more_questions = any(
                word in message_lower
                for word in ["also", "one more", "another", "wait", "actually"]
            )

            if more_questions:
                # Reset to greeting for new topic
                self.intent = None
                self.collected_slots = {}
                return ConversationState.GREETING

            # Stay in closing
            return ConversationState.CLOSING

        # Default: stay in current state
        return current

    def _set_required_slots(self):
        """Set required slots based on intent."""
        slot_requirements = {
            Intent.SCHEDULE_APPOINTMENT: [
                "customer_name",
                "phone_number",
                "email",
                "vehicle_year",
                "vehicle_make",
                "vehicle_model",
                "service_type",
                "preferred_date",
                "preferred_time",
            ],
            Intent.RESCHEDULE_APPOINTMENT: [
                "appointment_id",
                "new_date",
                "new_time",
            ],
            Intent.CANCEL_APPOINTMENT: [
                "appointment_id",
                "cancellation_reason",
            ],
        }

        # Adjust for existing customers (less info needed)
        if self.call_type == CallType.INBOUND_EXISTING:
            if self.intent == Intent.SCHEDULE_APPOINTMENT:
                # Don't need name, phone, email - already have it
                slot_requirements[Intent.SCHEDULE_APPOINTMENT] = [
                    "vehicle_selection",  # Which vehicle?
                    "service_type",
                    "preferred_date",
                    "preferred_time",
                ]

        self.required_slots = slot_requirements.get(self.intent, [])

    def _extract_slots(self, message: str):
        """
        Extract slot values from message.

        Note: This is a simplified extraction. In production, the LLM
        would extract structured data via function calls.
        """
        message_lower = message.lower()

        # Extract service type
        service_types = [
            "oil change",
            "brake service",
            "tire rotation",
            "inspection",
            "diagnostics",
            "maintenance",
            "repair",
        ]
        for service in service_types:
            if service in message_lower:
                self.collected_slots["service_type"] = service

        # Extract dates (basic patterns)
        date_patterns = [
            r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"(tomorrow|today)",
            r"\d{4}-\d{2}-\d{2}",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, message_lower)
            if match:
                self.collected_slots["preferred_date"] = match.group()

        # Extract times
        time_pattern = r"\b(\d{1,2})\s*(am|pm|:00|:30)\b"
        match = re.search(time_pattern, message_lower)
        if match:
            self.collected_slots["preferred_time"] = match.group()

        # In practice, the LLM would call tools to extract this info

    def _all_slots_collected(self) -> bool:
        """Check if all required slots have been collected."""
        return all(slot in self.collected_slots for slot in self.required_slots)

    def should_escalate(self, transcript: str = "") -> bool:
        """
        Detect if conversation should be escalated to human.

        Escalation triggers:
        - Customer anger/frustration
        - Request for manager/supervisor
        - Complex diagnostic questions
        - Warranty/insurance discussion
        - Complaint about previous service
        - Policy exceptions

        Args:
            transcript: Recent conversation text

        Returns:
            True if escalation needed
        """
        if self.escalation_triggered:
            return True

        transcript_lower = transcript.lower()

        # Escalation keyword patterns
        escalation_patterns = {
            "manager_request": [
                r"\b(manager|supervisor|owner|boss)\b",
                r"\bspeak to\b.*\b(someone|person|human)\b",
                r"\btransfer me\b",
            ],
            "anger": [
                r"\b(angry|furious|frustrated|ridiculous|unacceptable)\b",
                r"\bthis is (bullshit|bs|crap)\b",
                r"\b(sue|lawsuit|attorney|lawyer)\b",
            ],
            "complaint": [
                r"\b(complaint|complain|unhappy|dissatisfied)\b",
                r"\blast (time|service)\b.*\b(terrible|awful|bad|poor)\b",
                r"\bnever (coming back|using)\b",
            ],
            "complex": [
                r"\b(warranty|insurance claim|coverage)\b",
                r"\b(discount|exception|special case)\b",
                r"\bwhy (did|was)\b.*\b(charged|cost|price)\b",
            ],
        }

        # Check patterns
        for reason, patterns in escalation_patterns.items():
            for pattern in patterns:
                if re.search(pattern, transcript_lower):
                    self.escalation_reason = reason
                    logger.info(f"Escalation pattern matched: {reason}")
                    return True

        return False

    def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get summary of conversation state.

        Returns:
            Dict with conversation details
        """
        return {
            "call_type": self.call_type.value,
            "state": self.state.value,
            "intent": self.intent.value if self.intent else None,
            "turn_count": self.turn_count,
            "collected_slots": self.collected_slots,
            "required_slots": self.required_slots,
            "escalation_triggered": self.escalation_triggered,
            "escalation_reason": self.escalation_reason,
        }

    def verify_customer(self, verification_data: Dict[str, Any]) -> bool:
        """
        Verify customer identity.

        Args:
            verification_data: Dict with verification info
                - dob: Date of birth
                - phone_last_4: Last 4 digits of phone
                - address: Street address
                - vin: Vehicle VIN

        Returns:
            True if verification successful
        """
        if not self.customer_data:
            logger.warning("Cannot verify customer - no customer data")
            return False

        # Check date of birth
        if "dob" in verification_data:
            customer_dob = self.customer_data.get("date_of_birth")
            if customer_dob and verification_data["dob"] == customer_dob:
                logger.info("Customer verified via DOB")
                return True

        # Check phone last 4
        if "phone_last_4" in verification_data:
            customer_phone = self.customer_data.get("phone_number", "")
            last_4 = customer_phone[-4:] if len(customer_phone) >= 4 else ""
            if last_4 and verification_data["phone_last_4"] == last_4:
                logger.info("Customer verified via phone last 4")
                return True

        # Check address
        if "address" in verification_data:
            customer_address = self.customer_data.get("street_address", "").lower()
            provided_address = verification_data["address"].lower()
            if customer_address and provided_address in customer_address:
                logger.info("Customer verified via address")
                return True

        # Check VIN
        if "vin" in verification_data:
            vehicles = self.customer_data.get("vehicles", [])
            for vehicle in vehicles:
                if vehicle.get("vin") == verification_data["vin"]:
                    logger.info("Customer verified via VIN")
                    return True

        logger.warning("Customer verification failed")
        return False


# Convenience functions for creating conversation managers


def create_inbound_new_manager(caller_phone: str) -> ConversationManager:
    """Create conversation manager for new customer inbound call."""
    return ConversationManager(
        call_type=CallType.INBOUND_NEW,
        caller_phone=caller_phone,
    )


def create_inbound_existing_manager(
    caller_phone: str, customer_data: Dict[str, Any]
) -> ConversationManager:
    """Create conversation manager for existing customer inbound call."""
    return ConversationManager(
        call_type=CallType.INBOUND_EXISTING,
        caller_phone=caller_phone,
        customer_data=customer_data,
    )


def create_outbound_reminder_manager(
    customer_data: Dict[str, Any], appointment_data: Dict[str, Any]
) -> ConversationManager:
    """Create conversation manager for outbound reminder call."""
    return ConversationManager(
        call_type=CallType.OUTBOUND_REMINDER,
        customer_data=customer_data,
        appointment_data=appointment_data,
    )


def create_outbound_followup_manager(
    customer_data: Dict[str, Any], appointment_data: Dict[str, Any]
) -> ConversationManager:
    """Create conversation manager for outbound follow-up call."""
    return ConversationManager(
        call_type=CallType.OUTBOUND_FOLLOWUP,
        customer_data=customer_data,
        appointment_data=appointment_data,
    )
