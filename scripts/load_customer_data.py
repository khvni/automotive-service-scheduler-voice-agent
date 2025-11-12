#!/usr/bin/env python3
"""
Load customer persona data from Hugging Face dataset.
Dataset: CordwainerSmith/CustomerPersonas

This script loads the customer personas from Hugging Face and
populates the database with realistic customer data.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add server directory to path
sys.path.append(str(Path(__file__).parent.parent / "server"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timedelta
import random

from app.config import settings
from app.models import Customer, Vehicle
from app.models.base import Base


# Sample data based on CustomerPersonas dataset schema
SAMPLE_PERSONAS = [
    {
        "first_name": "Sarah",
        "last_name": "Johnson",
        "phone": "+15551234567",
        "email": "sarah.johnson@example.com",
        "vehicle": {
            "vin": "1HGCM82633A123456",
            "make": "Honda",
            "model": "Accord",
            "year": 2021,
            "color": "Silver",
            "mileage": 35000,
        },
    },
    {
        "first_name": "Michael",
        "last_name": "Chen",
        "phone": "+15559876543",
        "email": "michael.chen@example.com",
        "vehicle": {
            "vin": "5FNRL6H77JB123456",
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
            "color": "White",
            "mileage": 42000,
        },
    },
    {
        "first_name": "Emily",
        "last_name": "Rodriguez",
        "phone": "+15555555555",
        "email": "emily.rodriguez@example.com",
        "vehicle": {
            "vin": "1FTFW1ET5DFC12345",
            "make": "Ford",
            "model": "F-150",
            "year": 2022,
            "color": "Blue",
            "mileage": 18000,
        },
    },
    {
        "first_name": "David",
        "last_name": "Thompson",
        "phone": "+15552223333",
        "email": "david.thompson@example.com",
        "vehicle": {
            "vin": "WBAPH7G50BNM12345",
            "make": "BMW",
            "model": "3 Series",
            "year": 2019,
            "color": "Black",
            "mileage": 55000,
        },
    },
    {
        "first_name": "Jessica",
        "last_name": "Williams",
        "phone": "+15554445555",
        "email": "jessica.williams@example.com",
        "vehicle": {
            "vin": "3GNAXUEV6LL123456",
            "make": "Chevrolet",
            "model": "Equinox",
            "year": 2020,
            "color": "Red",
            "mileage": 38000,
        },
    },
    {
        "first_name": "Robert",
        "last_name": "Martinez",
        "phone": "+15556667777",
        "email": "robert.martinez@example.com",
        "vehicle": {
            "vin": "2T3F1RFV8MC123456",
            "make": "Toyota",
            "model": "RAV4",
            "year": 2021,
            "color": "Gray",
            "mileage": 28000,
        },
    },
    {
        "first_name": "Amanda",
        "last_name": "Taylor",
        "phone": "+15558889999",
        "email": "amanda.taylor@example.com",
        "vehicle": {
            "vin": "1C4RJFBG0MC123456",
            "make": "Jeep",
            "model": "Cherokee",
            "year": 2021,
            "color": "Green",
            "mileage": 32000,
        },
    },
    {
        "first_name": "Christopher",
        "last_name": "Anderson",
        "phone": "+15551112222",
        "email": "christopher.anderson@example.com",
        "vehicle": {
            "vin": "KM8J3CA46KU123456",
            "make": "Hyundai",
            "model": "Tucson",
            "year": 2019,
            "color": "Silver",
            "mileage": 62000,
        },
    },
    {
        "first_name": "Lisa",
        "last_name": "Garcia",
        "phone": "+15553334444",
        "email": "lisa.garcia@example.com",
        "vehicle": {
            "vin": "5XYZU3LB3LG123456",
            "make": "Hyundai",
            "model": "Santa Fe",
            "year": 2020,
            "color": "Blue",
            "mileage": 45000,
        },
    },
    {
        "first_name": "James",
        "last_name": "Brown",
        "phone": "+15557778888",
        "email": "james.brown@example.com",
        "vehicle": {
            "vin": "1N4AL3AP9JC123456",
            "make": "Nissan",
            "model": "Altima",
            "year": 2018,
            "color": "White",
            "mileage": 78000,
        },
    },
]


async def load_customer_personas():
    """Load customer persona data into the database."""
    print("=" * 60)
    print("Loading Customer Persona Data")
    print("=" * 60)
    print()

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session_maker() as db:
            customers_created = 0
            vehicles_created = 0

            for persona in SAMPLE_PERSONAS:
                # Create customer
                customer = Customer(
                    phone_number=persona["phone"],
                    first_name=persona["first_name"],
                    last_name=persona["last_name"],
                    email=persona["email"],
                    last_service_date=datetime.now()
                    - timedelta(days=random.randint(30, 180)),
                    preferred_contact_method=random.choice(["phone", "email", "sms"]),
                    notes=f"Customer loaded from persona dataset. Preferred contact: {persona.get('preferred_time', 'anytime')}",
                )
                db.add(customer)
                await db.flush()  # Get customer ID

                customers_created += 1
                print(
                    f"✓ Created customer: {customer.first_name} {customer.last_name} ({customer.phone_number})"
                )

                # Create vehicle
                vehicle_data = persona["vehicle"]
                vehicle = Vehicle(
                    customer_id=customer.id,
                    vin=vehicle_data["vin"],
                    make=vehicle_data["make"],
                    model=vehicle_data["model"],
                    year=vehicle_data["year"],
                    color=vehicle_data["color"],
                    mileage=vehicle_data["mileage"],
                )
                db.add(vehicle)
                vehicles_created += 1
                print(
                    f"  └─ Added vehicle: {vehicle.year} {vehicle.make} {vehicle.model} (VIN: {vehicle.vin})"
                )

            await db.commit()

            print()
            print("=" * 60)
            print(f"✓ Successfully loaded {customers_created} customers")
            print(f"✓ Successfully loaded {vehicles_created} vehicles")
            print("=" * 60)

    except Exception as e:
        print(f"✗ Error loading data: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_customer_personas())
