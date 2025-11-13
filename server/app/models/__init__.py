"""Database models for the application."""

from app.models.customer import Customer
from app.models.vehicle import Vehicle
from app.models.appointment import Appointment
from app.models.call_log import CallLog
from app.models.service_history import ServiceHistory

__all__ = ["Customer", "Vehicle", "Appointment", "CallLog", "ServiceHistory"]
