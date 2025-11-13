"""Vehicle model."""

import re

from app.models.base import Base, TimestampMixin
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship, validates


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
    service_history = relationship(
        "ServiceHistory", back_populates="vehicle", cascade="all, delete-orphan"
    )

    @validates("vin")
    def validate_vin(self, key, value):
        """Validate VIN format.

        HIGH PRIORITY FIX: Validates VIN format (17 characters, no I/O/Q).
        Enforces uppercase for consistency.
        """
        if not value:
            raise ValueError("VIN cannot be empty")

        # HIGH FIX: Enforce uppercase
        value = value.upper()

        # HIGH FIX: Validate VIN format - must be exactly 17 characters
        if len(value) != 17:
            raise ValueError(f"VIN must be exactly 17 characters, got {len(value)}")

        # HIGH FIX: VIN regex - alphanumeric excluding I, O, Q (easily confused with 1 and 0)
        vin_pattern = r"^[A-HJ-NPR-Z0-9]{17}$"
        if not re.match(vin_pattern, value):
            raise ValueError(
                f"Invalid VIN format: {value}. VIN must contain only letters (except I, O, Q) and numbers"
            )

        return value

    def __repr__(self):
        return f"<Vehicle(id={self.id}, vin='{self.vin}', {self.year} {self.make} {self.model})>"
