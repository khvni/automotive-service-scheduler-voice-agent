"""Service history model."""

from app.models.base import Base, TimestampMixin
from sqlalchemy import JSON, Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship


class ServiceHistory(Base, TimestampMixin):
    """Service history model for tracking vehicle service records.

    Stores detailed service history including:
    - Service date and mileage at time of service
    - Services performed and parts replaced
    - Cost of service
    - Next service recommendations
    """

    __tablename__ = "service_history"

    # Primary Identity
    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), index=True)

    # Service Performed
    service_date = Column(Date, nullable=False, index=True)
    mileage = Column(Integer)
    services_performed = Column(JSON)  # Array of services performed
    parts_replaced = Column(JSON)  # Array of parts replaced
    total_cost = Column(Numeric(10, 2))

    # Next Service Recommendation
    next_service_type = Column(String(100))
    next_service_due_date = Column(Date)
    next_service_due_mileage = Column(Integer)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="service_history")

    def __repr__(self):
        return (
            f"<ServiceHistory(id={self.id}, vehicle_id={self.vehicle_id}, "
            f"service_date='{self.service_date}')>"
        )
