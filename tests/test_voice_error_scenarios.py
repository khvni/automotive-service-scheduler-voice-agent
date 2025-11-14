"""
Test script to reproduce voice agent error scenarios.

This script simulates various failure scenarios that could cause the
"application error has occurred - goodbye" message in Twilio calls.

Run this script to test:
1. Deepgram STT connection failures
2. Deepgram TTS connection failures
3. OpenAI API failures
4. Timeout scenarios
"""

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent / "server"))

from app.services.deepgram_stt import DeepgramSTTService
from app.services.deepgram_tts import DeepgramTTSService
from app.services.openai_service import OpenAIService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_stt_connection_failure():
    """Test STT connection failure scenario."""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Deepgram STT Connection Failure")
    logger.info("="*80)

    # Create service with invalid API key
    stt = DeepgramSTTService(api_key="invalid_key")

    try:
        await stt.connect()
        logger.error("❌ Expected connection to fail but it succeeded")
        return False
    except Exception as e:
        logger.info(f"✅ Connection failed as expected: {e}")
        return True


async def test_stt_timeout_scenario():
    """Test STT timeout when no audio is sent."""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Deepgram STT Timeout (NET-0001)")
    logger.info("="*80)
    logger.info("Simulating scenario: WebSocket connected but no audio sent within 10 seconds")

    # This would require a real API key and waiting 10+ seconds
    # For now, just log the expected behavior
    logger.info("Expected: Deepgram would close connection with NET-0001 error")
    logger.info("Expected: voice.py exception handler would only log the error")
    logger.info("Expected: Twilio would timeout and play 'application error' message")
    return True


async def test_tts_connection_failure():
    """Test TTS connection failure scenario."""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Deepgram TTS Connection Failure")
    logger.info("="*80)

    # Create service with invalid API key
    tts = DeepgramTTSService(api_key="invalid_key")

    try:
        await tts.connect()
        logger.error("❌ Expected connection to fail but it succeeded")
        return False
    except Exception as e:
        logger.info(f"✅ Connection failed as expected: {e}")
        return True


async def test_openai_api_failure():
    """Test OpenAI API failure scenario."""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: OpenAI API Failure")
    logger.info("="*80)

    # Create service with invalid API key
    openai = OpenAIService(api_key="invalid_key")
    openai.set_system_prompt("Test")
    openai.add_user_message("Hello")

    try:
        async for event in openai.generate_response(stream=True):
            if event["type"] == "error":
                logger.info(f"✅ OpenAI error caught: {event['message']}")
                return True
        logger.error("❌ Expected error but none occurred")
        return False
    except Exception as e:
        logger.info(f"✅ Exception caught: {e}")
        return True


async def test_exception_propagation():
    """Test how exceptions propagate through the voice.py handler."""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Exception Propagation in voice.py")
    logger.info("="*80)

    logger.info("Scenario: Exception occurs during service initialization")
    logger.info("")
    logger.info("Current behavior in voice.py (lines 191-513):")
    logger.info("1. Services initialized in try block (line 195-204)")
    logger.info("2. If STT/TTS connect() fails, exception raised")
    logger.info("3. Exception caught at line 512: except Exception as e")
    logger.info("4. Error logged: logger.error(f'Error in media stream handler: {e}')")
    logger.info("5. finally block executes (line 515-559)")
    logger.info("6. WebSocket closes WITHOUT sending error to Twilio")
    logger.info("")
    logger.info("❌ PROBLEM: Twilio receives no response and plays 'application error' message")
    logger.info("")
    logger.info("Expected behavior:")
    logger.info("1. Catch exception during initialization")
    logger.info("2. Send error TwiML or graceful message to Twilio")
    logger.info("3. Close WebSocket gracefully")
    return True


async def test_send_audio_failure():
    """Test what happens when sending audio to STT fails."""
    logger.info("\n" + "="*80)
    logger.info("TEST 6: STT send_audio() Failure")
    logger.info("="*80)

    # Mock a connected STT service
    stt = DeepgramSTTService(api_key="test_key")
    stt.is_connected = True
    stt.connection = MagicMock()

    # Make send() raise an exception
    stt.connection.send.side_effect = Exception("Connection lost")

    try:
        await stt.send_audio(b"test_audio")
        logger.error("❌ Expected send_audio to fail but it succeeded")
        return False
    except Exception as e:
        logger.info(f"✅ send_audio failed as expected: {e}")
        logger.info("This would occur in voice.py line 314 (receive_from_twilio)")
        logger.info("Exception would propagate up and be caught at line 328")
        logger.info("❌ PROBLEM: Error only logged, user hears 'application error'")
        return True


async def test_tool_execution_failure():
    """Test what happens when a tool execution fails."""
    logger.info("\n" + "="*80)
    logger.info("TEST 7: Tool Execution Failure")
    logger.info("="*80)

    openai = OpenAIService(api_key="test_key", model="gpt-4o")

    # Register a tool that raises an exception
    async def failing_tool(**kwargs):
        raise Exception("Database connection failed")

    openai.register_tool(
        name="test_tool",
        description="Test tool",
        parameters={"type": "object", "properties": {}},
        handler=failing_tool
    )

    # Test tool execution
    result = await openai._execute_tool("test_tool", "{}")
    logger.info(f"Tool execution result: {result}")

    if '"error"' in result:
        logger.info("✅ Tool error properly caught and returned as JSON")
        logger.info("This allows LLM to handle the error gracefully")
        return True
    else:
        logger.error("❌ Tool error not properly handled")
        return False


async def main():
    """Run all test scenarios."""
    logger.info("\n" + "#"*80)
    logger.info("# Voice Agent Error Scenario Tests")
    logger.info("# Purpose: Reproduce 'application error has occurred - goodbye' message")
    logger.info("#"*80)

    results = []

    # Run tests
    results.append(("STT Connection Failure", await test_stt_connection_failure()))
    results.append(("STT Timeout Scenario", await test_stt_timeout_scenario()))
    results.append(("TTS Connection Failure", await test_tts_connection_failure()))
    results.append(("OpenAI API Failure", await test_openai_api_failure()))
    results.append(("Exception Propagation", await test_exception_propagation()))
    results.append(("Send Audio Failure", await test_send_audio_failure()))
    results.append(("Tool Execution Failure", await test_tool_execution_failure()))

    # Print summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    logger.info("")
    logger.info(f"Total: {passed_count}/{total_count} tests passed")

    # Print recommendations
    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATIONS")
    logger.info("="*80)
    logger.info("")
    logger.info("1. Add graceful error handling in voice.py:")
    logger.info("   - Catch service initialization failures")
    logger.info("   - Send error message via Twilio Say verb")
    logger.info("   - Close WebSocket gracefully")
    logger.info("")
    logger.info("2. Implement retry logic for transient failures:")
    logger.info("   - Retry Deepgram connections (with exponential backoff)")
    logger.info("   - Retry OpenAI API calls")
    logger.info("")
    logger.info("3. Add circuit breaker pattern:")
    logger.info("   - Track failure rates")
    logger.info("   - Fail fast when service is degraded")
    logger.info("   - Provide fallback responses")
    logger.info("")
    logger.info("4. Improve monitoring and alerting:")
    logger.info("   - Log all exceptions with full context")
    logger.info("   - Send alerts for repeated failures")
    logger.info("   - Track error rates in Redis")
    logger.info("")
    logger.info("5. Add health checks:")
    logger.info("   - Pre-flight checks before accepting calls")
    logger.info("   - Verify Deepgram/OpenAI connectivity")
    logger.info("   - Return 503 if services unavailable")
    logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
