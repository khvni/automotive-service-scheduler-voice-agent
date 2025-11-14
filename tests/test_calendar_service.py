"""
Test script for Google Calendar Service.

This script tests the CalendarService functionality:
1. OAuth2 authentication
2. Free/busy availability queries
3. Event creation
4. Event updates
5. Event cancellation
6. Event retrieval

Usage:
    python scripts/test_calendar_service.py

Requirements:
    - GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN set in .env
    - Valid Google Calendar API credentials
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.app.config import settings
from server.app.services.calendar_service import CalendarService


async def test_calendar_connection():
    """Test OAuth2 connection to Google Calendar."""
    print("\n" + "=" * 80)
    print("TEST 1: Calendar Service Connection")
    print("=" * 80)

    try:
        calendar = CalendarService(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            timezone_name=settings.CALENDAR_TIMEZONE,
        )

        # Try to get service (will authenticate)
        service = calendar.get_calendar_service()
        print("✓ Successfully connected to Google Calendar API")
        print(f"✓ Timezone: {calendar.timezone}")

        return calendar

    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return None


async def test_freebusy_query(calendar: CalendarService):
    """Test freebusy availability query."""
    print("\n" + "=" * 80)
    print("TEST 2: Free/Busy Availability Query")
    print("=" * 80)

    try:
        # Query tomorrow's availability (9 AM - 5 PM)
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = tomorrow.replace(hour=17, minute=0, second=0, microsecond=0)

        print(f"Querying availability for {start_time.date()}")
        print(f"Time range: {start_time.time()} - {end_time.time()}")

        free_slots = await calendar.get_free_availability(
            start_time=start_time, end_time=end_time, duration_minutes=30
        )

        print(f"\n✓ Found {len(free_slots)} available slots:")
        for i, slot in enumerate(free_slots[:5], 1):  # Show first 5 slots
            start_formatted = slot["start"].strftime("%I:%M %p")
            end_formatted = slot["end"].strftime("%I:%M %p")
            duration = (slot["end"] - slot["start"]).total_seconds() / 60
            print(f"  {i}. {start_formatted} - {end_formatted} ({int(duration)} min)")

        if len(free_slots) > 5:
            print(f"  ... and {len(free_slots) - 5} more slots")

        return free_slots

    except Exception as e:
        print(f"✗ Freebusy query failed: {e}")
        import traceback

        traceback.print_exc()
        return []


async def test_create_event(calendar: CalendarService):
    """Test calendar event creation."""
    print("\n" + "=" * 80)
    print("TEST 3: Create Calendar Event")
    print("=" * 80)

    try:
        # Create test event for 2 hours from now
        start_time = datetime.now() + timedelta(hours=2)
        end_time = start_time + timedelta(minutes=30)

        print(f"Creating test event:")
        print(f"  Title: Test Auto Service Appointment")
        print(f"  Time: {start_time.strftime('%Y-%m-%d %I:%M %p')}")

        result = await calendar.create_calendar_event(
            title="[TEST] Oil Change - John Doe",
            start_time=start_time,
            end_time=end_time,
            description="Test event created by calendar_service.py\n"
            "Customer: John Doe\n"
            "Phone: (555) 123-4567\n"
            "Vehicle: 2020 Honda Civic\n"
            "Service: Oil Change",
            attendees=None,  # No attendees for test
        )

        if result["success"]:
            print(f"✓ Event created successfully")
            print(f"  Event ID: {result['event_id']}")
            print(f"  Calendar Link: {result['calendar_link']}")
            return result["event_id"]
        else:
            print(f"✗ Failed to create event: {result['message']}")
            return None

    except Exception as e:
        print(f"✗ Event creation failed: {e}")
        import traceback

        traceback.print_exc()
        return None


async def test_get_event(calendar: CalendarService, event_id: str):
    """Test retrieving event details."""
    print("\n" + "=" * 80)
    print("TEST 4: Get Event Details")
    print("=" * 80)

    try:
        print(f"Fetching event: {event_id}")

        event = await calendar.get_event(event_id)

        if event:
            print(f"✓ Event retrieved successfully")
            print(f"  Summary: {event.get('summary')}")
            print(f"  Start: {event.get('start', {}).get('dateTime')}")
            print(f"  Status: {event.get('status')}")
            return True
        else:
            print(f"✗ Event not found")
            return False

    except Exception as e:
        print(f"✗ Get event failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_update_event(calendar: CalendarService, event_id: str):
    """Test updating calendar event."""
    print("\n" + "=" * 80)
    print("TEST 5: Update Calendar Event")
    print("=" * 80)

    try:
        # Update to 3 hours from now
        new_start_time = datetime.now() + timedelta(hours=3)
        new_end_time = new_start_time + timedelta(minutes=30)

        print(f"Updating event {event_id}")
        print(f"  New time: {new_start_time.strftime('%Y-%m-%d %I:%M %p')}")
        print(f"  New title: [TEST] Oil Change - John Doe (UPDATED)")

        result = await calendar.update_calendar_event(
            event_id=event_id,
            title="[TEST] Oil Change - John Doe (UPDATED)",
            start_time=new_start_time,
            end_time=new_end_time,
            description="Updated test event",
        )

        if result["success"]:
            print(f"✓ Event updated successfully")
            print(f"  Calendar Link: {result['calendar_link']}")
            return True
        else:
            print(f"✗ Failed to update event: {result['message']}")
            return False

    except Exception as e:
        print(f"✗ Event update failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_cancel_event(calendar: CalendarService, event_id: str):
    """Test canceling/deleting calendar event."""
    print("\n" + "=" * 80)
    print("TEST 6: Cancel Calendar Event")
    print("=" * 80)

    try:
        print(f"Cancelling event {event_id}")

        result = await calendar.cancel_calendar_event(event_id)

        if result["success"]:
            print(f"✓ Event cancelled successfully")
            return True
        else:
            print(f"✗ Failed to cancel event: {result['message']}")
            return False

    except Exception as e:
        print(f"✗ Event cancellation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all calendar service tests."""
    print("\n" + "=" * 80)
    print("GOOGLE CALENDAR SERVICE TEST SUITE")
    print("=" * 80)

    # Check environment variables
    if (
        not settings.GOOGLE_CLIENT_ID
        or settings.GOOGLE_CLIENT_ID == "your_client_id_here.apps.googleusercontent.com"
    ):
        print("\n✗ ERROR: Google Calendar credentials not configured")
        print("Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN in .env")
        print("\nSee .env.example for setup instructions")
        return

    # Test 1: Connection
    calendar = await test_calendar_connection()
    if not calendar:
        print("\n✗ Cannot proceed without valid calendar connection")
        return

    # Test 2: Freebusy query
    await test_freebusy_query(calendar)

    # Test 3: Create event
    event_id = await test_create_event(calendar)
    if not event_id:
        print("\n✗ Cannot proceed with update/cancel tests without event")
        return

    # Test 4: Get event
    await test_get_event(calendar, event_id)

    # Test 5: Update event
    await test_update_event(calendar, event_id)

    # Test 6: Cancel event
    await test_cancel_event(calendar, event_id)

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)
    print(
        "\nAll tests completed. Check your Google Calendar to verify events were created/updated/deleted."
    )
    print("\nNote: Test events are prefixed with [TEST] for easy identification")


async def run_integration_test():
    """
    Optional: Run integration test with real calendar data.

    This test:
    1. Queries real availability
    2. Creates a real appointment
    3. Reschedules it
    4. Cancels it
    """
    print("\n" + "=" * 80)
    print("INTEGRATION TEST (Optional)")
    print("=" * 80)
    print("\nThis test will create/modify actual calendar events.")
    print("Press Ctrl+C to skip, or wait 3 seconds to continue...")

    try:
        await asyncio.sleep(3)
    except KeyboardInterrupt:
        print("\n\nIntegration test skipped by user")
        return

    # Run integration test
    calendar = CalendarService(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        refresh_token=settings.GOOGLE_REFRESH_TOKEN,
        timezone_name=settings.CALENDAR_TIMEZONE,
    )

    # Query availability for next week
    next_week = datetime.now() + timedelta(days=7)
    start_time = next_week.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = next_week.replace(hour=17, minute=0, second=0, microsecond=0)

    print(f"\nChecking availability for {start_time.date()}...")
    free_slots = await calendar.get_free_availability(start_time, end_time, 60)

    if free_slots:
        # Book in first available slot
        first_slot = free_slots[0]
        print(f"\nBooking appointment in first available slot:")
        print(
            f"  {first_slot['start'].strftime('%I:%M %p')} - {first_slot['end'].strftime('%I:%M %p')}"
        )

        result = await calendar.create_calendar_event(
            title="[INTEGRATION TEST] Brake Inspection - Jane Smith",
            start_time=first_slot["start"],
            end_time=first_slot["start"] + timedelta(hours=1),
            description="Integration test appointment\nCustomer: Jane Smith\nVehicle: 2019 Toyota Camry",
        )

        if result["success"]:
            event_id = result["event_id"]
            print(f"✓ Appointment created: {event_id}")

            # Reschedule to second slot if available
            if len(free_slots) > 1:
                second_slot = free_slots[1]
                print(f"\nRescheduling to second slot:")
                print(
                    f"  {second_slot['start'].strftime('%I:%M %p')} - {second_slot['end'].strftime('%I:%M %p')}"
                )

                update_result = await calendar.update_calendar_event(
                    event_id=event_id,
                    start_time=second_slot["start"],
                    end_time=second_slot["start"] + timedelta(hours=1),
                )

                if update_result["success"]:
                    print(f"✓ Appointment rescheduled")

            # Cancel the test appointment
            print(f"\nCancelling test appointment...")
            cancel_result = await calendar.cancel_calendar_event(event_id)

            if cancel_result["success"]:
                print(f"✓ Appointment cancelled")

        print("\n✓ Integration test complete")
    else:
        print("\n✗ No available slots found for integration test")


if __name__ == "__main__":
    print(f"\nUsing configuration:")
    print(f"  Timezone: {settings.CALENDAR_TIMEZONE}")
    print(
        f"  Client ID: {settings.GOOGLE_CLIENT_ID[:20]}..."
        if settings.GOOGLE_CLIENT_ID
        else "  Client ID: Not set"
    )
    print(
        f"  Refresh Token: {settings.GOOGLE_REFRESH_TOKEN[:20]}..."
        if settings.GOOGLE_REFRESH_TOKEN
        else "  Refresh Token: Not set"
    )

    # Run main test suite
    asyncio.run(run_all_tests())

    # Optionally run integration test
    # Uncomment to enable:
    # asyncio.run(run_integration_test())
