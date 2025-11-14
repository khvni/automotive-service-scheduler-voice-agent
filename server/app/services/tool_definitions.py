"""
Tool schema definitions for OpenAI function calling.

This module defines the function schemas that the LLM can call during conversations.
Each tool follows the OpenAI function calling specification format.
"""

from typing import Any, Dict, List, Optional

# Tool schemas for OpenAI function calling
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_customer",
            "description": "Look up customer information by phone number. Returns customer details, vehicles, and service history if found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {
                        "type": "string",
                        "description": "Customer's phone number (10 digits, formats accepted: 555-123-4567, (555) 123-4567, or 5551234567)",
                    }
                },
                "required": ["phone_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Get available appointment time slots for a specific date. Returns list of available times for booking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to check availability (format: YYYY-MM-DD, e.g., 2025-01-15)",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Appointment duration in minutes. Common values: 30 (quick service), 60 (standard service), 90 (complex work). Default: 30",
                        "default": 30,
                    },
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a service appointment for a customer. Creates appointment in system and Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "Customer ID (obtained from lookup_customer result)",
                    },
                    "vehicle_id": {
                        "type": "integer",
                        "description": "Vehicle ID (obtained from lookup_customer result)",
                    },
                    "scheduled_at": {
                        "type": "string",
                        "description": "Appointment start time in ISO format (e.g., '2025-01-15T09:00:00')",
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Type of service to book (e.g., 'oil_change', 'brake_service', 'inspection')",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes (default: 60)",
                        "default": 60,
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any special notes or customer concerns (optional)",
                    },
                },
                "required": ["customer_id", "vehicle_id", "scheduled_at", "service_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_appointments",
            "description": "Get list of upcoming appointments for a customer. Returns scheduled appointments with dates and service types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "integer",
                        "description": "Customer ID (obtained from lookup_customer)",
                    }
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. Updates system and removes from calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "Appointment ID to cancel (obtained from get_upcoming_appointments)",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancellation (optional but helpful for tracking)",
                        "enum": [
                            "schedule_conflict",
                            "got_service_elsewhere",
                            "vehicle_sold",
                            "issue_resolved",
                            "other",
                        ],
                    },
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new time. Updates system and calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "integer",
                        "description": "Appointment ID to reschedule (obtained from get_upcoming_appointments)",
                    },
                    "new_datetime": {
                        "type": "string",
                        "description": "New appointment datetime in ISO format (e.g., '2025-01-16T14:00:00')",
                    },
                },
                "required": ["appointment_id", "new_datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decode_vin",
            "description": "Decode a vehicle VIN number to get make, model, year, and other vehicle information from NHTSA database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vin": {
                        "type": "string",
                        "description": "17-character Vehicle Identification Number (VIN)",
                    }
                },
                "required": ["vin"],
            },
        },
    },
]


def get_tool_schema_by_name(tool_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific tool schema by name.

    Args:
        tool_name: Name of the tool to retrieve

    Returns:
        Tool schema dict or None if not found
    """
    for schema in TOOL_SCHEMAS:
        if schema["function"]["name"] == tool_name:
            return schema
    return None


def get_all_tool_names() -> List[str]:
    """
    Get list of all available tool names.

    Returns:
        List of tool names
    """
    return [schema["function"]["name"] for schema in TOOL_SCHEMAS]
