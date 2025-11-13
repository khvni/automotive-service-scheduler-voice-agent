"""Customer model."""

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Text
from sqlalchemy.orm import relationship, validates

from app.models.base import Base, TimestampMixin

# US state codes for validation
US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
}


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

    @validates('phone_number')
    def validate_phone_number(self, key, value):
        """Validate phone number length."""
        if value and len(value) > 20:
            raise ValueError(f"Phone number must be <= 20 characters, got {len(value)}")
        return value

    @validates('email')
    def validate_email(self, key, value):
        """Validate email length."""
        if value and len(value) > 255:
            raise ValueError(f"Email must be <= 255 characters, got {len(value)}")
        return value

    @validates('state')
    def validate_state(self, key, value):
        """Validate US state code."""
        if value and value.upper() not in US_STATES:
            raise ValueError(f"Invalid US state code: {value}")
        return value.upper() if value else value

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.first_name} {self.last_name}', phone='{self.phone_number}')>"
