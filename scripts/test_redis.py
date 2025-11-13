#!/usr/bin/env python3
"""Test script for Redis session management and customer caching."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from datetime import datetime
from app.services import redis_client
from app.config import settings


async def test_session_management():
    """Test session CRUD operations."""
    print("\n" + "="*70)
    print("Testing Session Management")
    print("="*70)

    test_call_sid = "test_call_12345"

    # Test 1: Create session
    print("\n1. Creating session...")
    session_data = {
        "call_sid": test_call_sid,
        "stream_sid": "test_stream_12345",
        "caller_phone": "+15551234567",
        "customer_id": 42,
        "conversation_history": [
            {
                "role": "assistant",
                "content": "Hello! How can I help you today?",
                "timestamp": datetime.utcnow().isoformat()
            }
        ],
        "current_state": "greeting",
        "collected_data": {},
        "intent": None,
        "speaking": False
    }

    success = await redis_client.set_session(test_call_sid, session_data, ttl=60)
    if success:
        print("   ✓ Session created successfully")
    else:
        print("   ✗ Failed to create session")
        return False

    # Test 2: Retrieve session
    print("\n2. Retrieving session...")
    retrieved = await redis_client.get_session(test_call_sid)
    if retrieved:
        print("   ✓ Session retrieved successfully")
        print(f"   - Call SID: {retrieved.get('call_sid')}")
        print(f"   - Caller: {retrieved.get('caller_phone')}")
        print(f"   - State: {retrieved.get('current_state')}")
        print(f"   - Created: {retrieved.get('created_at')}")
    else:
        print("   ✗ Failed to retrieve session")
        return False

    # Test 3: Update session
    print("\n3. Updating session...")
    updates = {
        "current_state": "collecting_info",
        "intent": "book_appointment",
        "collected_data": {
            "service_type": "oil_change"
        },
        "conversation_history": [
            *retrieved.get("conversation_history", []),
            {
                "role": "user",
                "content": "I need an oil change",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    }

    success = await redis_client.update_session(test_call_sid, updates)
    if success:
        updated = await redis_client.get_session(test_call_sid)
        print("   ✓ Session updated successfully")
        print(f"   - New state: {updated.get('current_state')}")
        print(f"   - Intent: {updated.get('intent')}")
        print(f"   - Collected data: {updated.get('collected_data')}")
    else:
        print("   ✗ Failed to update session")
        return False

    # Test 4: Delete session
    print("\n4. Deleting session...")
    success = await redis_client.delete_session(test_call_sid)
    if success:
        print("   ✓ Session deleted successfully")

        # Verify deletion
        retrieved = await redis_client.get_session(test_call_sid)
        if retrieved is None:
            print("   ✓ Verified: session no longer exists")
        else:
            print("   ✗ Warning: session still exists after deletion")
    else:
        print("   ✗ Failed to delete session")
        return False

    return True


async def test_customer_caching():
    """Test customer cache operations."""
    print("\n" + "="*70)
    print("Testing Customer Caching")
    print("="*70)

    test_phone = "+15551234567"

    # Test 1: Cache customer
    print("\n1. Caching customer data...")
    customer_data = {
        "id": 42,
        "phone_number": test_phone,
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "vehicles": [
            {
                "id": 1,
                "make": "Toyota",
                "model": "Camry",
                "year": 2020,
                "vin": "1HGBH41JXMN109186"
            }
        ],
        "upcoming_appointments": [
            {
                "id": 5,
                "service_type": "Oil Change",
                "date": "2025-11-15T10:00:00"
            }
        ],
        "last_service_date": "2025-09-01T14:30:00"
    }

    success = await redis_client.cache_customer(test_phone, customer_data, ttl=30)
    if success:
        print("   ✓ Customer cached successfully")
    else:
        print("   ✗ Failed to cache customer")
        return False

    # Test 2: Retrieve cached customer
    print("\n2. Retrieving cached customer...")
    cached = await redis_client.get_cached_customer(test_phone)
    if cached:
        print("   ✓ Customer cache hit")
        print(f"   - Name: {cached.get('first_name')} {cached.get('last_name')}")
        print(f"   - Email: {cached.get('email')}")
        print(f"   - Vehicles: {len(cached.get('vehicles', []))}")
        print(f"   - Upcoming appointments: {len(cached.get('upcoming_appointments', []))}")
        print(f"   - Cached at: {cached.get('cached_at')}")
    else:
        print("   ✗ Customer cache miss")
        return False

    # Test 3: Invalidate cache
    print("\n3. Invalidating customer cache...")
    success = await redis_client.invalidate_customer_cache(test_phone)
    if success:
        print("   ✓ Customer cache invalidated")

        # Verify invalidation
        cached = await redis_client.get_cached_customer(test_phone)
        if cached is None:
            print("   ✓ Verified: customer no longer in cache")
        else:
            print("   ✗ Warning: customer still in cache after invalidation")
    else:
        print("   ✗ Failed to invalidate cache")
        return False

    return True


async def test_ttl_expiration():
    """Test TTL (Time-To-Live) expiration."""
    print("\n" + "="*70)
    print("Testing TTL Expiration")
    print("="*70)

    test_call_sid = "test_ttl_session"

    # Create session with short TTL
    print("\n1. Creating session with 3-second TTL...")
    session_data = {
        "call_sid": test_call_sid,
        "stream_sid": "test_stream",
        "caller_phone": "+15559999999",
        "customer_id": None,
        "conversation_history": [],
        "current_state": "greeting",
        "collected_data": {},
        "intent": None,
        "speaking": False
    }

    success = await redis_client.set_session(test_call_sid, session_data, ttl=3)
    if success:
        print("   ✓ Session created with 3s TTL")
    else:
        print("   ✗ Failed to create session")
        return False

    # Verify it exists
    print("\n2. Verifying session exists immediately...")
    retrieved = await redis_client.get_session(test_call_sid)
    if retrieved:
        print("   ✓ Session found")
    else:
        print("   ✗ Session not found (should exist)")
        return False

    # Wait for expiration
    print("\n3. Waiting 4 seconds for TTL expiration...")
    await asyncio.sleep(4)

    # Verify it's gone
    print("\n4. Checking if session expired...")
    retrieved = await redis_client.get_session(test_call_sid)
    if retrieved is None:
        print("   ✓ Session expired as expected")
    else:
        print("   ✗ Session still exists (should have expired)")
        return False

    return True


async def test_health_check():
    """Test Redis health check."""
    print("\n" + "="*70)
    print("Testing Health Check")
    print("="*70)

    print("\n1. Running Redis health check...")
    is_healthy = await redis_client.check_redis_health()

    if is_healthy:
        print("   ✓ Redis is healthy and accessible")
    else:
        print("   ✗ Redis health check failed")
        return False

    return True


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("Redis Session Management Test Suite")
    print("="*70)
    print(f"Redis URL: {settings.REDIS_URL}")

    try:
        # Initialize Redis
        print("\nInitializing Redis connection...")
        await redis_client.init_redis()
        print("✓ Redis connected")

        # Run tests
        results = []

        results.append(("Health Check", await test_health_check()))
        results.append(("Session Management", await test_session_management()))
        results.append(("Customer Caching", await test_customer_caching()))
        results.append(("TTL Expiration", await test_ttl_expiration()))

        # Summary
        print("\n" + "="*70)
        print("Test Summary")
        print("="*70)

        passed = 0
        failed = 0

        for test_name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{test_name:<30} {status}")
            if result:
                passed += 1
            else:
                failed += 1

        print(f"\nTotal: {passed + failed} tests, {passed} passed, {failed} failed")

        if failed == 0:
            print("\n🎉 All tests passed!")
            exit_code = 0
        else:
            print(f"\n⚠️  {failed} test(s) failed")
            exit_code = 1

    except Exception as e:
        print(f"\n✗ Error during tests: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1

    finally:
        # Close Redis
        print("\nClosing Redis connection...")
        await redis_client.close_redis()
        print("✓ Redis disconnected")

    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
