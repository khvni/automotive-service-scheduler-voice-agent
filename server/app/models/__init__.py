"""Database models for the application."""

from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.appointment import Appointment
from app.models.call_log import CallLog

__all__ = ["Customer", "Vehicle", "Appointment", "CallLog"]
