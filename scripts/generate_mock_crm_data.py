#!/usr/bin/env python3
"""
Generate mock CRM data for development and testing.

This script generates realistic customer, vehicle, appointment, and service history data
using the Faker library. It creates:
- 10,000 customers with comprehensive profile information
- ~16,000 vehicles (1.6 per customer average)
- ~8,000 appointments (70% past, 15% future, 15% cancelled)
- Service history records for completed appointments
"""

import asyncio
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add server directory to path
sys.path.append(str(Path(__file__).parent.parent / "server"))

from app.config import settings
from app.models import Appointment, Customer, ServiceHistory, Vehicle
from app.models.appointment import AppointmentStatus, ServiceType
from app.models.base import Base
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Initialize Faker
fake = Faker("en_US")
Faker.seed(42)  # For reproducibility
random.seed(42)

# Constants for realistic data generation
MAKES_MODELS = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Tacoma", "4Runner", "Tundra", "Prius"],
    "Honda": ["Accord", "Civic", "CR-V", "Pilot", "Odyssey", "Ridgeline", "HR-V"],
    "Ford": ["F-150", "Escape", "Explorer", "Mustang", "Edge", "Bronco", "Ranger"],
    "Chevrolet": ["Silverado", "Equinox", "Malibu", "Tahoe", "Traverse", "Colorado"],
    "BMW": ["3 Series", "5 Series", "X3", "X5", "X7", "7 Series"],
    "Mercedes-Benz": ["C-Class", "E-Class", "GLC", "GLE", "GLS", "S-Class"],
    "Nissan": ["Altima", "Sentra", "Rogue", "Pathfinder", "Frontier", "Murano"],
    "Hyundai": ["Elantra", "Sonata", "Tucson", "Santa Fe", "Kona", "Palisade"],
    "Jeep": ["Wrangler", "Cherokee", "Grand Cherokee", "Compass", "Gladiator"],
    "Subaru": ["Outback", "Forester", "Crosstrek", "Impreza", "Ascent"],
}

SERVICE_TYPES = [
    ServiceType.OIL_CHANGE,
    ServiceType.TIRE_ROTATION,
    ServiceType.BRAKE_INSPECTION,
    ServiceType.BRAKE_SERVICE,
    ServiceType.ENGINE_DIAGNOSTICS,
    ServiceType.INSPECTION,
    ServiceType.GENERAL_MAINTENANCE,
]

SERVICE_CATEGORIES = ["maintenance", "repair", "inspection", "recall"]

SERVICE_ADVISORS = [
    "Mike Johnson",
    "Sarah Chen",
    "Robert Williams",
    "Emily Davis",
    "James Martinez",
]

TECHNICIANS = ["Tom Anderson", "Lisa Thompson", "Carlos Rodriguez", "Amanda White", "Kevin Brown"]

SERVICE_BAYS = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]


def generate_vin():
    """Generate a realistic VIN number."""
    # Simple VIN generation (17 characters)
    chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"  # pragma: allowlist secret
    return "".join(random.choice(chars) for _ in range(17))


def generate_license_plate():
    """Generate a realistic license plate."""
    formats = [
        lambda: f"{random.randint(0, 9)}{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}",
        lambda: f"{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}{random.randint(1000, 9999)}",
        lambda: f"{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}",
    ]
    return random.choice(formats)()


async def generate_customers(num_customers: int = 10000):
    """Generate comprehensive customer data."""
    print(f"Generating {num_customers} customers...")
    customers = []

    for i in range(num_customers):
        if (i + 1) % 1000 == 0:
            print(f"  Generated {i + 1} customers...")

        first_name = fake.first_name()
        last_name = fake.last_name()

        # Generate realistic date of birth (ages 18-75)
        age = random.randint(18, 75)
        dob = date.today() - timedelta(days=age * 365 + random.randint(0, 365))

        # Customer since date (random between 6 months and 5 years ago)
        customer_since = fake.date_between(start_date="-5y", end_date="-6M")

        # Last contact date (between customer_since and now)
        last_contact = None
        if random.random() < 0.7:  # 70% have been contacted
            last_contact = fake.date_time_between(start_date=customer_since, end_date="now")

        customer = Customer(
            # Contact
            phone_number=fake.phone_number(),
            email=f"{first_name.lower()}.{last_name.lower()}.{random.randint(1, 999)}@{fake.free_email_domain()}",
            preferred_contact_method=random.choices(
                ["phone", "email", "sms"], weights=[0.70, 0.20, 0.10]
            )[0],
            # Personal
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            # Address
            street_address=fake.street_address(),
            city=fake.city(),
            state=fake.state_abbr(),
            zip_code=fake.zipcode(),
            # Relationship
            customer_since=customer_since,
            customer_type=random.choices(
                ["retail", "fleet", "referral"], weights=[0.85, 0.05, 0.10]
            )[0],
            referral_source=fake.name() if random.random() < 0.1 else None,
            preferred_service_advisor=random.choice(SERVICE_ADVISORS + [None, None]),
            # Preferences
            receive_reminders=random.choice([True, True, True, False]),
            receive_promotions=random.choice([True, True, False]),
            preferred_appointment_time=random.choice(
                ["morning", "afternoon", "evening", None, None]
            ),
            # Notes (occasionally)
            notes=fake.sentence() if random.random() < 0.15 else None,
            # Timestamps
            last_contact_date=last_contact,
        )
        customers.append(customer)

    return customers


async def generate_vehicles(customers: list):
    """Generate vehicles with service history awareness."""
    print("Generating vehicles...")
    vehicles = []
    vehicle_count = 0

    for i, customer in enumerate(customers):
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1} customers, generated {vehicle_count} vehicles...")

        # Number of vehicles per customer (weighted: 65% have 1, 25% have 2, 10% have 3)
        num_vehicles = random.choices([1, 2, 3], weights=[0.65, 0.25, 0.10])[0]

        for idx in range(num_vehicles):
            make = random.choice(list(MAKES_MODELS.keys()))
            model = random.choice(MAKES_MODELS[make])
            year = random.randint(2010, 2024)

            # Determine if purchased from us (50% chance)
            purchased_from_us = random.choice([True, False])
            purchase_date = None
            if purchased_from_us and customer.customer_since:
                # Purchase date between customer_since and 1 year later
                latest_purchase = min(customer.customer_since + timedelta(days=365), date.today())
                purchase_date = fake.date_between(
                    start_date=customer.customer_since, end_date=latest_purchase
                )

            # Calculate mileage based on vehicle age
            age_years = 2024 - year
            annual_mileage = random.randint(10000, 15000)
            base_mileage = age_years * annual_mileage
            current_mileage = base_mileage + random.randint(0, 5000)

            # Last service (60% have service history)
            last_service_date = None
            last_service_mileage = None
            if random.random() < 0.6 and customer.customer_since:
                last_service_date = fake.date_between(
                    start_date=customer.customer_since, end_date=date.today()
                )
                last_service_mileage = current_mileage - random.randint(500, 3000)

            vehicle = Vehicle(
                customer_id=customer.id,
                # Identity
                vin=generate_vin(),
                license_plate=generate_license_plate(),
                # Details
                year=year,
                make=make,
                model=model,
                trim=random.choice(["Base", "LX", "EX", "Limited", "Premium", "Sport", None]),
                color=fake.color_name(),
                # Ownership
                purchase_date=purchase_date,
                purchased_from_us=purchased_from_us,
                # Service
                current_mileage=current_mileage,
                last_service_date=last_service_date,
                last_service_mileage=last_service_mileage,
                next_service_due_mileage=current_mileage + random.randint(2000, 5000),
                # Status
                is_primary_vehicle=(idx == 0),  # First vehicle is primary
                status="active",
            )
            vehicles.append(vehicle)
            vehicle_count += 1

    print(f"Generated {vehicle_count} total vehicles")
    return vehicles


async def generate_appointments(customers: list, vehicles: list):
    """Generate appointments with realistic distribution."""
    print("Generating appointments...")
    appointments = []

    # Create a mapping of customer_id to their vehicles
    customer_vehicles = {}
    for vehicle in vehicles:
        if vehicle.customer_id not in customer_vehicles:
            customer_vehicles[vehicle.customer_id] = []
        customer_vehicles[vehicle.customer_id].append(vehicle)

    # Generate appointments for ~50% of customers
    customers_with_appts = random.sample(customers, k=int(len(customers) * 0.5))

    appointment_count = 0
    for i, customer in enumerate(customers_with_appts):
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1} customers, generated {appointment_count} appointments...")

        # Skip if customer has no vehicles
        if customer.id not in customer_vehicles:
            continue

        # Number of appointments (1-3, weighted towards 1)
        num_appointments = random.choices([1, 2, 3], weights=[0.70, 0.20, 0.10])[0]

        customer_vehicle_list = customer_vehicles[customer.id]

        for _ in range(num_appointments):
            vehicle = random.choice(customer_vehicle_list)

            # Determine appointment timing
            # 70% past, 15% future, 15% cancelled
            status_choice = random.choices(
                ["past", "future", "cancelled"], weights=[0.70, 0.15, 0.15]
            )[0]

            if status_choice == "past":
                # Past appointment (completed)
                scheduled_at = fake.date_time_between(
                    start_date=customer.customer_since or "-2y", end_date="-1d"
                )
                status = AppointmentStatus.COMPLETED
                completed_at = scheduled_at + timedelta(hours=random.randint(1, 4))
            elif status_choice == "future":
                # Future appointment
                scheduled_at = fake.date_time_between(start_date="now", end_date="+90d")
                status = random.choice([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
                completed_at = None
            else:
                # Cancelled appointment
                scheduled_at = fake.date_time_between(
                    start_date=customer.customer_since or "-2y", end_date="now"
                )
                status = random.choice([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
                completed_at = None

            service_type = random.choice(SERVICE_TYPES)
            service_category = random.choice(SERVICE_CATEGORIES)

            # Generate cost
            cost_ranges = {
                ServiceType.OIL_CHANGE: (30, 80),
                ServiceType.TIRE_ROTATION: (25, 50),
                ServiceType.BRAKE_INSPECTION: (40, 80),
                ServiceType.BRAKE_SERVICE: (200, 600),
                ServiceType.ENGINE_DIAGNOSTICS: (100, 300),
                ServiceType.INSPECTION: (50, 100),
                ServiceType.GENERAL_MAINTENANCE: (80, 250),
            }

            min_cost, max_cost = cost_ranges.get(service_type, (50, 200))
            estimated_cost = Decimal(random.randint(min_cost, max_cost))

            # Actual cost is usually close to estimated for completed
            actual_cost = None
            if status == AppointmentStatus.COMPLETED:
                variance = random.uniform(0.9, 1.2)
                # HIGH FIX: Use Decimal(str()) pattern to prevent precision loss
                # Converting float directly to Decimal can introduce rounding errors
                actual_cost = (Decimal(str(estimated_cost)) * Decimal(str(variance))).quantize(
                    Decimal("0.01")
                )

            appointment = Appointment(
                customer_id=customer.id,
                vehicle_id=vehicle.id,
                # Appointment Details
                scheduled_at=scheduled_at,
                duration_minutes=random.choice([30, 60, 90, 120]),
                service_type=service_type,
                service_category=service_category,
                # Service Details
                service_description=f"{service_type.value.replace('_', ' ').title()} for {vehicle.year} {vehicle.make} {vehicle.model}",
                customer_concerns=fake.sentence() if random.random() < 0.5 else None,
                recommended_services=fake.sentence() if random.random() < 0.3 else None,
                estimated_cost=estimated_cost,
                actual_cost=actual_cost,
                # Status & Workflow
                status=status,
                cancellation_reason=(
                    fake.sentence() if status == AppointmentStatus.CANCELLED else None
                ),
                confirmation_sent=(
                    random.choice([True, False]) if status != AppointmentStatus.CANCELLED else False
                ),
                reminder_sent=(
                    random.choice([True, False]) if status != AppointmentStatus.CANCELLED else False
                ),
                # Assignment
                assigned_technician=(
                    random.choice(TECHNICIANS) if status == AppointmentStatus.COMPLETED else None
                ),
                service_bay=(
                    random.choice(SERVICE_BAYS) if status == AppointmentStatus.COMPLETED else None
                ),
                # Communication
                booking_method=random.choice(["phone", "online", "walk_in", "ai_voice"]),
                booked_by=random.choice(SERVICE_ADVISORS + ["AI Voice Agent"]),
                # Timestamps
                completed_at=completed_at,
            )
            appointments.append(appointment)
            appointment_count += 1

    print(f"Generated {appointment_count} total appointments")
    return appointments


async def generate_service_history(appointments: list):
    """Generate service history for completed appointments."""
    print("Generating service history records...")
    history_records = []

    completed_appointments = [
        apt for apt in appointments if apt.status == AppointmentStatus.COMPLETED
    ]

    for i, appointment in enumerate(completed_appointments):
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1} appointments...")

        # Generate services performed
        services_performed = [appointment.service_type.value]
        if random.random() < 0.3:  # 30% chance of additional services
            additional_services = random.sample(
                [
                    "filter_replacement",
                    "fluid_top_off",
                    "tire_pressure_check",
                    "battery_test",
                    "wiper_replacement",
                ],
                k=random.randint(1, 2),
            )
            services_performed.extend(additional_services)

        # Generate parts replaced (if applicable)
        parts_replaced = []
        if appointment.service_type in [ServiceType.OIL_CHANGE, ServiceType.BRAKE_SERVICE]:
            if appointment.service_type == ServiceType.OIL_CHANGE:
                parts_replaced = ["oil_filter", "engine_oil"]
            elif appointment.service_type == ServiceType.BRAKE_SERVICE:
                parts_replaced = random.sample(
                    [
                        "brake_pads_front",
                        "brake_pads_rear",
                        "brake_rotors_front",
                        "brake_rotors_rear",
                        "brake_fluid",
                    ],
                    k=random.randint(1, 3),
                )

        # Next service recommendation
        next_service_type = random.choice(
            ["Oil Change", "Tire Rotation", "Brake Inspection", "Multi-Point Inspection"]
        )

        # Next service due in 3-6 months
        next_due_date = appointment.scheduled_at.date() + timedelta(days=random.randint(90, 180))
        next_due_mileage = random.randint(3000, 7000)

        history = ServiceHistory(
            vehicle_id=appointment.vehicle_id,
            appointment_id=appointment.id,
            service_date=appointment.scheduled_at.date(),
            mileage=random.randint(10000, 150000),  # Should ideally match vehicle mileage at time
            services_performed=services_performed,
            parts_replaced=parts_replaced if parts_replaced else None,
            total_cost=appointment.actual_cost,
            next_service_type=next_service_type,
            next_service_due_date=next_due_date,
            next_service_due_mileage=next_due_mileage,
        )
        history_records.append(history)

    print(f"Generated {len(history_records)} service history records")
    return history_records


async def main():
    """Main function to generate and load all mock data."""
    print("=" * 70)
    print("Mock CRM Data Generator")
    print("=" * 70)

    # Connect to database
    print("\nConnecting to database...")
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create tables
    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully!")

    # Generate data
    print("\n" + "=" * 70)
    print("Generating Mock Data")
    print("=" * 70)

    customers = await generate_customers(num_customers=10000)

    # Insert customers in batches
    print("\nInserting customers into database...")
    async with async_session_maker() as db:
        db.add_all(customers)
        await db.commit()

        # Refresh to get IDs
        for customer in customers:
            await db.refresh(customer)
    print("Customers inserted successfully!")

    # Generate and insert vehicles
    vehicles = await generate_vehicles(customers)
    print("\nInserting vehicles into database...")
    async with async_session_maker() as db:
        db.add_all(vehicles)
        await db.commit()

        # Refresh to get IDs
        for vehicle in vehicles:
            await db.refresh(vehicle)
    print("Vehicles inserted successfully!")

    # Generate and insert appointments
    appointments = await generate_appointments(customers, vehicles)
    print("\nInserting appointments into database...")
    async with async_session_maker() as db:
        db.add_all(appointments)
        await db.commit()

        # Refresh to get IDs
        for appointment in appointments:
            await db.refresh(appointment)
    print("Appointments inserted successfully!")

    # Generate and insert service history
    service_history = await generate_service_history(appointments)
    print("\nInserting service history into database...")
    async with async_session_maker() as db:
        db.add_all(service_history)
        await db.commit()
    print("Service history inserted successfully!")

    # Print summary
    print("\n" + "=" * 70)
    print("Data Generation Complete!")
    print("=" * 70)
    print(f"Customers:       {len(customers):,}")
    print(f"Vehicles:        {len(vehicles):,}")
    print(f"Appointments:    {len(appointments):,}")
    print(f"Service History: {len(service_history):,}")
    print("=" * 70)

    # Print some statistics
    completed_appts = len([a for a in appointments if a.status == AppointmentStatus.COMPLETED])
    future_appts = len(
        [
            a
            for a in appointments
            if a.status in [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]
        ]
    )
    cancelled_appts = len(
        [
            a
            for a in appointments
            if a.status in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]
        ]
    )

    print("\nAppointment Statistics:")
    print(f"  Completed:  {completed_appts:,} ({completed_appts/len(appointments)*100:.1f}%)")
    print(f"  Future:     {future_appts:,} ({future_appts/len(appointments)*100:.1f}%)")
    print(f"  Cancelled:  {cancelled_appts:,} ({cancelled_appts/len(appointments)*100:.1f}%)")

    await engine.dispose()
    print("\nDatabase connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
