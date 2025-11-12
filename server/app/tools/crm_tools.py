"""CRM tools for customer and appointment management."""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, Vehicle, Appointment


async def lookup_customer(
    db: AsyncSession, phone_number: str
) -> Optional[Dict[str, Any]]:
    """
    Look up customer by phone number.

    Args:
        db: Database session
        phone_number: Customer phone number

    Returns:
        Customer information if found, None otherwise
    """
    result = await db.execute(
        select(Customer).where(Customer.phone_number == phone_number)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        return None

    return {
        "id": customer.id,
        "name": f"{customer.first_name} {customer.last_name}",
        "email": customer.email,
        "phone": customer.phone_number,
        "last_service_date": customer.last_service_date.isoformat()
        if customer.last_service_date
        else None,
        "notes": customer.notes,
    }


async def create_customer(
    db: AsyncSession,
    phone_number: str,
    first_name: str,
    last_name: str,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new customer.

    Args:
        db: Database session
        phone_number: Customer phone number
        first_name: First name
        last_name: Last name
        email: Email address (optional)

    Returns:
        Created customer information
    """
    customer = Customer(
        phone_number=phone_number,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    return {
        "id": customer.id,
        "name": f"{customer.first_name} {customer.last_name}",
        "email": customer.email,
        "phone": customer.phone_number,
    }


async def get_customer_vehicles(
    db: AsyncSession, customer_id: int
) -> list[Dict[str, Any]]:
    """
    Get all vehicles for a customer.

    Args:
        db: Database session
        customer_id: Customer ID

    Returns:
        List of vehicles
    """
    result = await db.execute(
        select(Vehicle).where(Vehicle.customer_id == customer_id)
    )
    vehicles = result.scalars().all()

    return [
        {
            "id": v.id,
            "vin": v.vin,
            "year": v.year,
            "make": v.make,
            "model": v.model,
            "color": v.color,
        }
        for v in vehicles
    ]
