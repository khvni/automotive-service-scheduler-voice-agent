"""Customer model."""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    """Customer model for storing customer information."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255), unique=True, index=True)
    preferred_contact_method = Column(String(20), default="phone")  # phone, email, sms
    notes = Column(String(1000))
    last_service_date = Column(DateTime)

    # Relationships
    vehicles = relationship("Vehicle", back_populates="customer", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="customer", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.first_name} {self.last_name}', phone='{self.phone_number}')>"
