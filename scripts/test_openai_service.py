#!/usr/bin/env python3
"""
Test script for OpenAI GPT-4o service.

This script tests the core functionality of the OpenAI service including:
- Connection and initialization
- System prompt setting
- Tool registration
- Streaming responses
- Tool calling
- Conversation history
- Token usage tracking
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# Add server directory to path
server_dir = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_dir))

from app.services.openai_service import OpenAIService
from app.services.system_prompts import build_system_prompt, INBOUND_NEW_CUSTOMER_PROMPT
from app.config import settings


# Mock tool handlers for testing
async def mock_lookup_customer(phone_number: str):
    """Mock customer lookup."""
    await asyncio.sleep(0.1)  # Simulate database query
    return {
        "found": True,
        "customer": {
            "id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "phone": phone_number,
            "email": "john.doe@example.com",
            "vehicles": [
                {
                    "id": 1,
                    "year": 2020,
                    "make": "Honda",
                    "model": "Civic",
                }
            ]
        }
    }


async def mock_get_available_slots(date: str, service_type: str = "general_service"):
    """Mock availability check."""
    await asyncio.sleep(0.1)  # Simulate calendar query
    return {
        "date": date,
        "available_slots": [
            {"time": "09:00", "available": True},
            {"time": "11:00", "available": True},
            {"time": "14:00", "available": True},
        ]
    }


async def mock_book_appointment(
    customer_id: int,
    vehicle_id: int,
    service_type: str,
    start_time: str,
    notes: str = ""
):
    """Mock appointment booking."""
    await asyncio.sleep(0.1)  # Simulate booking
    return {
        "booked": True,
        "appointment_id": 123,
        "service_type": service_type,
        "start_time": start_time,
    }


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def test_initialization():
    """Test 1: Service initialization."""
    print_section("Test 1: Service Initialization")

    try:
        service = OpenAIService(
            api_key=settings.OPENAI_API_KEY,
            model="gpt-4o",
            temperature=0.8,
        )
        print("✓ OpenAI service initialized successfully")
        print(f"  Model: {service.model}")
        print(f"  Temperature: {service.temperature}")
        print(f"  Max tokens: {service.max_tokens}")
        return service
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return None


async def test_system_prompt(service: OpenAIService):
    """Test 2: System prompt setting."""
    print_section("Test 2: System Prompt")

    try:
        # Test with pre-built prompt
        service.set_system_prompt(INBOUND_NEW_CUSTOMER_PROMPT)
        print("✓ System prompt set successfully")

        history = service.get_conversation_history()
        print(f"  History length: {len(history)}")
        print(f"  First message role: {history[0]['role']}")
        print(f"  Prompt preview: {history[0]['content'][:100]}...")

        # Test dynamic prompt building
        custom_prompt = build_system_prompt(
            "inbound_existing",
            customer_context={
                "name": "Sarah Johnson",
                "customer_since": "2023-01-15",
                "last_service": "Oil change",
                "last_service_date": "2024-12-01",
                "vehicles": "2020 Honda Civic",
                "upcoming_appointments": "None"
            }
        )
        service.set_system_prompt(custom_prompt)
        print("✓ Dynamic system prompt built and set")

    except Exception as e:
        print(f"✗ System prompt test failed: {e}")


async def test_tool_registration(service: OpenAIService):
    """Test 3: Tool registration."""
    print_section("Test 3: Tool Registration")

    try:
        # Register mock tools
        service.register_tool(
            name="lookup_customer",
            description="Look up customer by phone",
            parameters={
                "type": "object",
                "properties": {
                    "phone_number": {"type": "string"}
                },
                "required": ["phone_number"]
            },
            handler=mock_lookup_customer
        )

        service.register_tool(
            name="get_available_slots",
            description="Get available time slots",
            parameters={
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "service_type": {"type": "string"}
                },
                "required": ["date"]
            },
            handler=mock_get_available_slots
        )

        service.register_tool(
            name="book_appointment",
            description="Book an appointment",
            parameters={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "integer"},
                    "vehicle_id": {"type": "integer"},
                    "service_type": {"type": "string"},
                    "start_time": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["customer_id", "vehicle_id", "service_type", "start_time"]
            },
            handler=mock_book_appointment
        )

        print(f"✓ Registered {len(service.tool_schemas)} tools")
        for schema in service.tool_schemas:
            print(f"  - {schema['function']['name']}")

    except Exception as e:
        print(f"✗ Tool registration failed: {e}")


async def test_simple_conversation(service: OpenAIService):
    """Test 4: Simple conversation without tool calls."""
    print_section("Test 4: Simple Conversation")

    try:
        # Clear history and set simple prompt
        service.clear_history(keep_system=False)
        service.set_system_prompt("You are a helpful assistant. Keep responses brief (1-2 sentences).")

        # Add user message
        service.add_user_message("Say hello in a friendly way.")

        print("Generating response...")
        start_time = time.time()
        first_token_time = None
        full_response = ""

        async for event in service.generate_response(stream=True):
            if event["type"] == "content_delta":
                if first_token_time is None:
                    first_token_time = time.time() - start_time
                full_response += event["text"]
                print(event["text"], end="", flush=True)

            elif event["type"] == "done":
                total_time = time.time() - start_time
                print(f"\n\n✓ Response complete")
                print(f"  Time to first token: {first_token_time:.3f}s")
                print(f"  Total response time: {total_time:.3f}s")
                print(f"  Tokens used: {event['usage']}")

            elif event["type"] == "error":
                print(f"\n✗ Error: {event['message']}")
                return

    except Exception as e:
        print(f"✗ Conversation test failed: {e}")


async def test_tool_calling(service: OpenAIService):
    """Test 5: Tool calling functionality."""
    print_section("Test 5: Tool Calling")

    try:
        # Clear and setup for tool calling
        service.clear_history(keep_system=False)
        service.set_system_prompt(
            "You are Sophie at Bart's Automotive. Help customers schedule appointments. "
            "Use the lookup_customer tool to find customer information."
        )

        # Simulate customer request
        service.add_user_message("Hi, I'd like to schedule an oil change. My number is 555-1234.")

        print("Generating response with tool calls...")
        start_time = time.time()
        tool_calls_made = []

        async for event in service.generate_response(stream=True):
            if event["type"] == "content_delta":
                print(event["text"], end="", flush=True)

            elif event["type"] == "tool_call":
                tool_calls_made.append(event["name"])
                print(f"\n[Tool Call: {event['name']}]")
                print(f"  Arguments: {event['arguments']}")

            elif event["type"] == "tool_result":
                print(f"[Tool Result: {event['result'][:100]}...]")

            elif event["type"] == "done":
                total_time = time.time() - start_time
                print(f"\n\n✓ Tool calling complete")
                print(f"  Total time: {total_time:.3f}s")
                print(f"  Tools called: {', '.join(tool_calls_made) if tool_calls_made else 'None'}")
                print(f"  Tokens used: {event['usage']}")

            elif event["type"] == "error":
                print(f"\n✗ Error: {event['message']}")
                return

    except Exception as e:
        print(f"✗ Tool calling test failed: {e}")


async def test_conversation_history(service: OpenAIService):
    """Test 6: Conversation history management."""
    print_section("Test 6: Conversation History")

    try:
        history = service.get_conversation_history()
        print(f"✓ History retrieved: {len(history)} messages")

        for i, msg in enumerate(history[-5:]):  # Last 5 messages
            role = msg["role"]
            content = msg.get("content", "[tool call]")
            preview = content[:50] if isinstance(content, str) else "[non-text]"
            print(f"  {i+1}. {role}: {preview}...")

        # Test token counting
        token_count = service.get_conversation_token_count()
        print(f"\n✓ Estimated conversation tokens: {token_count}")

        # Test history clearing
        service.clear_history(keep_system=True)
        new_history = service.get_conversation_history()
        print(f"✓ History cleared: {len(new_history)} messages remaining")

    except Exception as e:
        print(f"✗ History test failed: {e}")


async def test_performance(service: OpenAIService):
    """Test 7: Performance metrics."""
    print_section("Test 7: Performance Metrics")

    try:
        service.clear_history(keep_system=False)
        service.set_system_prompt("You are a helpful assistant. Answer in 1-2 sentences.")

        # Make 3 quick requests
        times = []
        for i in range(3):
            service.add_user_message(f"Tell me a fact about the number {i+1}.")

            start = time.time()
            first_token = None

            async for event in service.generate_response(stream=True):
                if event["type"] == "content_delta" and first_token is None:
                    first_token = time.time() - start
                elif event["type"] == "done":
                    times.append(first_token)
                    break

        print(f"✓ Performance test complete")
        print(f"  Average time to first token: {sum(times) / len(times):.3f}s")
        print(f"  Min: {min(times):.3f}s, Max: {max(times):.3f}s")

        usage = service.get_token_usage()
        print(f"\n✓ Total session usage:")
        print(f"  Prompt tokens: {usage['prompt_tokens']}")
        print(f"  Completion tokens: {usage['completion_tokens']}")
        print(f"  Total tokens: {usage['total_tokens']}")

    except Exception as e:
        print(f"✗ Performance test failed: {e}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  OpenAI GPT-4o Service Test Suite")
    print("=" * 60)

    # Check for API key
    if not settings.OPENAI_API_KEY:
        print("\n✗ OPENAI_API_KEY not set in environment")
        print("  Please set it in .env file or environment variables")
        return

    print(f"\nAPI Key: {settings.OPENAI_API_KEY[:10]}...{settings.OPENAI_API_KEY[-4:]}")
    print(f"Model: {settings.OPENAI_MODEL}")

    # Run tests
    service = await test_initialization()
    if not service:
        return

    await test_system_prompt(service)
    await test_tool_registration(service)
    await test_simple_conversation(service)
    await test_tool_calling(service)
    await test_conversation_history(service)
    await test_performance(service)

    # Summary
    print_section("Test Suite Complete")
    print("All tests executed. Check results above for any failures.")
    print("\nNext steps:")
    print("  1. Review any failed tests")
    print("  2. Test with real CRM tools (Feature 6)")
    print("  3. Integrate with WebSocket handler (Feature 8)")
    print("  4. Test end-to-end with STT and TTS")


if __name__ == "__main__":
    asyncio.run(main())
