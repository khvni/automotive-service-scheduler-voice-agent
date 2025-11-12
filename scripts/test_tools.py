#!/usr/bin/env python3
"""
Test script for CRM, Calendar, and VIN tools.
"""

import asyncio
import sys
from pathlib import Path

# Add server directory to path
sys.path.append(str(Path(__file__).parent.parent / "server"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timedelta

from app.config import settings
from app.tools.crm_tools import lookup_customer, get_customer_vehicles
from app.tools.vin_tools import decode_vin, suggest_service_for_vehicle


async def test_crm_tools():
    """Test CRM tools."""
    print("\n=== Testing CRM Tools ===\n")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as db:
        # Test lookup_customer
        print("Testing lookup_customer...")
        customer = await lookup_customer(db, "+15551234567")
        if customer:
            print(f"✓ Found customer: {customer['name']}")
            print(f"  Email: {customer['email']}")
            print(f"  Phone: {customer['phone']}")

            # Test get_customer_vehicles
            print("\nTesting get_customer_vehicles...")
            vehicles = await get_customer_vehicles(db, customer["id"])
            print(f"✓ Found {len(vehicles)} vehicle(s)")
            for vehicle in vehicles:
                print(f"  - {vehicle['year']} {vehicle['make']} {vehicle['model']}")
        else:
            print("✗ Customer not found")

    await engine.dispose()


async def test_vin_tools():
    """Test VIN decoding tools."""
    print("\n=== Testing VIN Tools ===\n")

    # Test with a valid VIN
    test_vin = "1HGBH41JXMN109186"  # Honda Accord
    print(f"Testing decode_vin with VIN: {test_vin}")

    vehicle_info = await decode_vin(test_vin)
    if vehicle_info:
        print(f"✓ VIN decoded successfully:")
        print(f"  Make: {vehicle_info.get('make')}")
        print(f"  Model: {vehicle_info.get('model')}")
        print(f"  Year: {vehicle_info.get('year')}")
    else:
        print("✗ Failed to decode VIN")

    # Test service suggestions
    print("\nTesting suggest_service_for_vehicle...")
    suggestions = await suggest_service_for_vehicle(year=2018, mileage=55000)
    print(f"✓ Service suggestions for 2018 vehicle with 55k miles:")
    for suggestion in suggestions:
        print(f"  - {suggestion}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("AI Automotive Service Scheduler - Tool Testing")
    print("=" * 60)

    await test_crm_tools()
    await test_vin_tools()

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
