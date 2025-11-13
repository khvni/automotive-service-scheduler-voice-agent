"""Vehicle model."""

from sqlalchemy import Column, Integer, String, ForeignKey, Date, Boolean, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Vehicle(Base, TimestampMixin):
    """Vehicle model for storing vehicle information.

    Stores comprehensive vehicle data including:
    - Vehicle identification (VIN, license plate)
    - Vehicle specifications (make, model, year, trim, color)
    - Ownership information
    - Service history and mileage tracking
    - Vehicle status
    """

    __tablename__ = "vehicles"

    # Primary Identity
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)

    # Vehicle Identification
    vin = Column(String(17), unique=True, nullable=False, index=True)
    license_plate = Column(String(20), index=True)

    # Vehicle Details
    year = Column(Integer)
    make = Column(String(100))
    model = Column(String(100))
    trim = Column(String(50))
    color = Column(String(50))

    # Ownership Information
    purchase_date = Column(Date)
    purchased_from_us = Column(Boolean, default=False)

    # Service Information
    current_mileage = Column(Integer)
    last_service_date = Column(Date)
    last_service_mileage = Column(Integer)
    next_service_due_mileage = Column(Integer)

    # Vehicle Status
    is_primary_vehicle = Column(Boolean, default=True)
    status = Column(String(20), default="active")  # active, sold, totaled

    # Notes
    notes = Column(Text)

    # Relationships
    customer = relationship("Customer", back_populates="vehicles")
    appointments = relationship("Appointment", back_populates="vehicle")
    service_history = relationship("ServiceHistory", back_populates="vehicle", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vehicle(id={self.id}, vin='{self.vin}', {self.year} {self.make} {self.model})>"
