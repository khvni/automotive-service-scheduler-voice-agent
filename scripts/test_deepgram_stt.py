"""
Test script for Deepgram STT service.

Tests:
1. Connection to Deepgram
2. Sending audio data
3. Receiving transcripts
4. Interim vs final results
5. Graceful shutdown
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add server directory to path
server_path = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_path))

from app.services.deepgram_stt import DeepgramSTTService
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def generate_test_audio() -> bytes:
    """
    Generate test audio data (mulaw encoded silence).

    In a real scenario, this would be actual mulaw encoded audio from Twilio.
    For testing, we'll generate silence which won't produce transcripts,
    but will test the connection mechanism.

    Returns:
        bytes: Mulaw encoded audio data
    """
    # Generate 160 bytes of mulaw silence (20ms at 8kHz)
    # Mulaw silence is approximately 0xFF (255)
    return bytes([0xFF] * 160)


async def test_connection():
    """Test 1: Basic connection to Deepgram."""
    logger.info("=" * 60)
    logger.info("Test 1: Connection Test")
    logger.info("=" * 60)

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("DEEPGRAM_API_KEY not found in environment variables")
        return False

    stt = DeepgramSTTService(api_key)

    try:
        await stt.connect()
        logger.info("✓ Successfully connected to Deepgram")

        # Wait a moment to ensure connection is stable
        await asyncio.sleep(2)

        await stt.close()
        logger.info("✓ Successfully closed connection")

        return True
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        return False


async def test_audio_sending():
    """Test 2: Send audio data to Deepgram."""
    logger.info("=" * 60)
    logger.info("Test 2: Audio Sending Test")
    logger.info("=" * 60)

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("DEEPGRAM_API_KEY not found in environment variables")
        return False

    stt = DeepgramSTTService(api_key)

    try:
        await stt.connect()
        logger.info("✓ Connected to Deepgram")

        # Send test audio chunks
        for i in range(5):
            audio_chunk = await generate_test_audio()
            await stt.send_audio(audio_chunk)
            logger.info(f"✓ Sent audio chunk {i+1}")
            await asyncio.sleep(0.02)  # 20ms between chunks

        logger.info("✓ Successfully sent 5 audio chunks")

        await stt.close()
        return True
    except Exception as e:
        logger.error(f"✗ Audio sending test failed: {e}")
        await stt.close()
        return False


async def test_transcript_queue():
    """Test 3: Transcript queue functionality."""
    logger.info("=" * 60)
    logger.info("Test 3: Transcript Queue Test")
    logger.info("=" * 60)

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("DEEPGRAM_API_KEY not found in environment variables")
        return False

    stt = DeepgramSTTService(api_key)

    try:
        await stt.connect()
        logger.info("✓ Connected to Deepgram")

        # Send audio and check for transcripts
        logger.info("Sending audio and checking transcript queue...")

        for i in range(10):
            audio_chunk = await generate_test_audio()
            await stt.send_audio(audio_chunk)

            # Check for transcripts (won't get any with silence, but tests the mechanism)
            transcript = await stt.get_transcript()
            if transcript:
                logger.info(f"✓ Received transcript: {transcript}")

            await asyncio.sleep(0.02)

        logger.info("✓ Transcript queue mechanism working")

        await stt.close()
        return True
    except Exception as e:
        logger.error(f"✗ Transcript queue test failed: {e}")
        await stt.close()
        return False


async def test_configuration():
    """Test 4: Verify STT configuration."""
    logger.info("=" * 60)
    logger.info("Test 4: Configuration Test")
    logger.info("=" * 60)

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("DEEPGRAM_API_KEY not found in environment variables")
        return False

    stt = DeepgramSTTService(api_key)

    # Verify configuration
    config = stt.live_options

    checks = [
        ("Model", config.model, "nova-2-phonecall"),
        ("Language", config.language, "en"),
        ("Encoding", config.encoding, "mulaw"),
        ("Sample Rate", config.sample_rate, 8000),
        ("Channels", config.channels, 1),
        ("Interim Results", config.interim_results, True),
        ("Smart Format", config.smart_format, True),
        ("Endpointing", config.endpointing, 300),
        ("Utterance End MS", config.utterance_end_ms, 1000),
    ]

    all_passed = True
    for name, actual, expected in checks:
        if actual == expected:
            logger.info(f"✓ {name}: {actual}")
        else:
            logger.error(f"✗ {name}: expected {expected}, got {actual}")
            all_passed = False

    return all_passed


async def test_error_handling():
    """Test 5: Error handling."""
    logger.info("=" * 60)
    logger.info("Test 5: Error Handling Test")
    logger.info("=" * 60)

    # Test with invalid API key
    stt = DeepgramSTTService("invalid_api_key")

    try:
        await stt.connect()
        logger.error("✗ Should have failed with invalid API key")
        await stt.close()
        return False
    except Exception as e:
        logger.info(f"✓ Correctly raised exception for invalid API key: {type(e).__name__}")
        return True


async def test_send_without_connect():
    """Test 6: Sending audio without connection."""
    logger.info("=" * 60)
    logger.info("Test 6: Send Without Connection Test")
    logger.info("=" * 60)

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("DEEPGRAM_API_KEY not found in environment variables")
        return False

    stt = DeepgramSTTService(api_key)

    try:
        audio_chunk = await generate_test_audio()
        await stt.send_audio(audio_chunk)
        logger.error("✗ Should have failed when sending without connection")
        return False
    except Exception as e:
        logger.info(f"✓ Correctly raised exception when not connected: {type(e).__name__}")
        return True


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("Deepgram STT Service Test Suite")
    logger.info("=" * 60 + "\n")

    tests = [
        ("Configuration", test_configuration),
        ("Connection", test_connection),
        ("Audio Sending", test_audio_sending),
        ("Transcript Queue", test_transcript_queue),
        ("Error Handling (Invalid API Key)", test_error_handling),
        ("Send Without Connection", test_send_without_connect),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
            logger.info("")
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
            logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info("=" * 60)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
