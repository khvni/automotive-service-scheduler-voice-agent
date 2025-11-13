"""Customer model."""

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Customer(Base, TimestampMixin):
    """Customer model for storing customer information.

    Stores comprehensive customer data including:
    - Contact information for multi-channel communication
    - Personal information for identity verification
    - Address details for service delivery
    - Customer relationship metadata
    - Preferences for personalized service
    """

    __tablename__ = "customers"

    # Primary Identity
    id = Column(Integer, primary_key=True, index=True)

    # Contact Information
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, index=True)
    preferred_contact_method = Column(String(20), default="phone")  # phone, email, sms

    # Personal Information
    first_name = Column(String(100))
    last_name = Column(String(100))
    date_of_birth = Column(Date)  # For verification

    # Address Information
    street_address = Column(String(200))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))

    # Customer Relationship
    customer_since = Column(Date)
    customer_type = Column(String(20), default="retail")  # retail, fleet, referral
    referral_source = Column(String(100))  # Who referred them
    preferred_service_advisor = Column(String(100))

    # Preferences
    receive_reminders = Column(Boolean, default=True)
    receive_promotions = Column(Boolean, default=True)
    preferred_appointment_time = Column(String(20))  # morning, afternoon, evening

    # Notes and Metadata
    notes = Column(Text)  # Service advisor notes
    last_service_date = Column(DateTime)
    last_contact_date = Column(DateTime)

    # Relationships
    vehicles = relationship("Vehicle", back_populates="customer", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="customer", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="customer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.first_name} {self.last_name}', phone='{self.phone_number}')>"
