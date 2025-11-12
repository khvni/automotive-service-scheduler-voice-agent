"""Appointment model."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base, TimestampMixin


class AppointmentStatus(str, enum.Enum):
    """Appointment status enum."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class ServiceType(str, enum.Enum):
    """Service type enum."""

    OIL_CHANGE = "oil_change"
    TIRE_ROTATION = "tire_rotation"
    BRAKE_SERVICE = "brake_service"
    INSPECTION = "inspection"
    GENERAL_MAINTENANCE = "general_maintenance"
    REPAIR = "repair"
    DIAGNOSTIC = "diagnostic"
    OTHER = "other"


class Appointment(Base, TimestampMixin):
    """Appointment model for storing appointment information."""

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"))

    # Appointment details
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=60)
    service_type = Column(SQLEnum(ServiceType), default=ServiceType.GENERAL_MAINTENANCE)
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.PENDING, index=True)

    # Service details
    service_description = Column(String(1000))
    estimated_cost = Column(Integer)  # in cents
    actual_cost = Column(Integer)  # in cents

    # Calendar integration
    google_calendar_event_id = Column(String(255), unique=True, index=True)

    notes = Column(String(2000))

    # Relationships
    customer = relationship("Customer", back_populates="appointments")
    vehicle = relationship("Vehicle", back_populates="appointments")

    def __repr__(self):
        return f"<Appointment(id={self.id}, customer_id={self.customer_id}, scheduled_at='{self.scheduled_at}', status='{self.status}')>"
