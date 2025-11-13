"""Appointment model."""

import enum

from app.models.base import Base, TimestampMixin
from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship


class AppointmentStatus(str, enum.Enum):
    """Appointment status enum."""

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class ServiceType(str, enum.Enum):
    """Service type enum."""

    OIL_CHANGE = "oil_change"
    TIRE_ROTATION = "tire_rotation"
    BRAKE_SERVICE = "brake_service"
    BRAKE_INSPECTION = "brake_inspection"
    INSPECTION = "inspection"
    ENGINE_DIAGNOSTICS = "engine_diagnostics"
    GENERAL_MAINTENANCE = "general_maintenance"
    REPAIR = "repair"
    DIAGNOSTIC = "diagnostic"
    RECALL = "recall"
    OTHER = "other"


class Appointment(Base, TimestampMixin):
    """Appointment model for storing appointment information.

    Stores comprehensive appointment data including:
    - Scheduling details and timing
    - Service type and category
    - Customer concerns and recommendations
    - Cost estimates and actuals
    - Status and workflow tracking
    - Communication tracking (confirmations, reminders)
    - Calendar integration
    - Assignment to technicians and service bays
    """

    __tablename__ = "appointments"

    # HIGH FIX: Add composite indexes for optimized queries
    __table_args__ = (
        # HIGH FIX: Index for querying appointments by status and scheduled time
        Index("ix_appointments_status_scheduled", "status", "scheduled_at"),
        # HIGH FIX: Index for querying customer appointments by scheduled time
        Index("ix_appointments_customer_scheduled", "customer_id", "scheduled_at"),
    )

    # Primary Identity
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    # HIGH FIX: Set vehicle_id nullable=False to ensure data integrity
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)

    # Appointment Details
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=60)
    service_type = Column(SQLEnum(ServiceType), default=ServiceType.GENERAL_MAINTENANCE)
    service_category = Column(String(50))  # maintenance, repair, inspection, recall

    # Service Details
    service_description = Column(Text)
    customer_concerns = Column(Text)  # What the customer reported
    recommended_services = Column(Text)  # What we recommend
    estimated_cost = Column(Numeric(10, 2))  # Using Decimal for currency
    actual_cost = Column(Numeric(10, 2))  # Using Decimal for currency

    # Status & Workflow
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.SCHEDULED, index=True)
    cancellation_reason = Column(String(200))
    confirmation_sent = Column(Boolean, default=False)
    reminder_sent = Column(Boolean, default=False)

    # External Integration
    calendar_event_id = Column(String(255))  # Google Calendar ID

    # Assignment
    assigned_technician = Column(String(100))
    service_bay = Column(String(10))

    # Communication History
    booking_method = Column(String(20))  # phone, online, walk_in, ai_voice
    booked_by = Column(String(100))  # Agent name or 'AI Voice Agent'

    # Notes
    notes = Column(Text)

    # Timestamps
    completed_at = Column(DateTime)

    # Relationships
    customer = relationship("Customer", back_populates="appointments")
    vehicle = relationship("Vehicle", back_populates="appointments")

    def __repr__(self):
        return f"<Appointment(id={self.id}, customer_id={self.customer_id}, scheduled_at='{self.scheduled_at}', status='{self.status}')>"
