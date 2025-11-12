"""Vehicle model."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class Vehicle(Base, TimestampMixin):
    """Vehicle model for storing vehicle information."""

    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    vin = Column(String(17), unique=True, index=True)
    make = Column(String(100))
    model = Column(String(100))
    year = Column(Integer)
    color = Column(String(50))
    license_plate = Column(String(20))
    mileage = Column(Integer)
    notes = Column(String(1000))

    # Relationships
    customer = relationship("Customer", back_populates="vehicles")
    appointments = relationship("Appointment", back_populates="vehicle")

    def __repr__(self):
        return f"<Vehicle(id={self.id}, vin='{self.vin}', {self.year} {self.make} {self.model})>"
