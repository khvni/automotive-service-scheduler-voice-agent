#!/usr/bin/env python3
"""
Test script for Deepgram TTS service.

Tests:
1. Connection establishment
2. Text synthesis (single chunk)
3. Streaming synthesis (multiple chunks)
4. Flush command
5. Clear command (barge-in)
6. Performance metrics (time-to-first-byte)

Usage:
    python scripts/test_deepgram_tts.py
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.app.services.deepgram_tts import DeepgramTTSService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_connection(tts: DeepgramTTSService) -> bool:
    """
    Test 1: Connection establishment.

    Verifies that WebSocket connection to Deepgram TTS can be established.
    """
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Connection Establishment")
    logger.info("=" * 70)

    try:
        await tts.connect()

        if tts.is_connected:
            logger.info("✓ Connection established successfully")
            return True
        else:
            logger.error("✗ Connection failed: is_connected is False")
            return False

    except Exception as e:
        logger.error(f"✗ Connection failed with exception: {e}")
        return False


async def test_text_synthesis(tts: DeepgramTTSService) -> bool:
    """
    Test 2: Basic text synthesis.

    Sends a single text chunk and verifies audio is received.
    """
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Basic Text Synthesis")
    logger.info("=" * 70)

    try:
        test_text = "Hello, this is a test of the Deepgram text to speech system."
        logger.info(f"Sending text: {test_text}")

        # Send text
        await tts.send_text(test_text)

        # Flush to ensure all audio is generated
        await tts.flush()

        # Wait for audio to be generated
        logger.info("Waiting for audio generation...")
        await asyncio.sleep(2)

        # Collect all audio chunks
        audio_chunks = []
        while True:
            audio = await tts.get_audio()
            if audio is None:
                break
            audio_chunks.append(audio)

        if audio_chunks:
            total_bytes = sum(len(chunk) for chunk in audio_chunks)
            logger.info(
                f"✓ Received {len(audio_chunks)} audio chunks, " f"total {total_bytes} bytes"
            )
            return True
        else:
            logger.error("✗ No audio received")
            return False

    except Exception as e:
        logger.error(f"✗ Text synthesis failed: {e}")
        return False


async def test_streaming_synthesis(tts: DeepgramTTSService) -> bool:
    """
    Test 3: Streaming text synthesis.

    Sends multiple text chunks and verifies audio streaming works correctly.
    """
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Streaming Text Synthesis")
    logger.info("=" * 70)

    try:
        text_chunks = [
            "Welcome to Premium Auto Service. ",
            "We're here to help you schedule your appointment. ",
            "What type of service do you need today? ",
        ]

        logger.info(f"Sending {len(text_chunks)} text chunks...")

        # Send chunks one by one
        for i, chunk in enumerate(text_chunks, 1):
            logger.info(f"Chunk {i}/{len(text_chunks)}: {chunk}")
            await tts.send_text(chunk)
            await asyncio.sleep(0.5)  # Small delay between chunks

        # Flush to finalize
        await tts.flush()

        # Wait for audio generation
        logger.info("Waiting for audio generation...")
        await asyncio.sleep(3)

        # Collect all audio
        audio_chunks = []
        while True:
            audio = await tts.get_audio()
            if audio is None:
                break
            audio_chunks.append(audio)

        if audio_chunks:
            total_bytes = sum(len(chunk) for chunk in audio_chunks)
            logger.info(
                f"✓ Streaming successful: {len(audio_chunks)} chunks, " f"{total_bytes} bytes"
            )
            return True
        else:
            logger.error("✗ No audio received from streaming")
            return False

    except Exception as e:
        logger.error(f"✗ Streaming synthesis failed: {e}")
        return False


async def test_flush_command(tts: DeepgramTTSService) -> bool:
    """
    Test 4: Flush command.

    Verifies that flush properly finalizes audio generation.
    """
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Flush Command")
    logger.info("=" * 70)

    try:
        # Send text
        test_text = "Testing flush command."
        logger.info(f"Sending text: {test_text}")
        await tts.send_text(test_text)

        # Flush
        logger.info("Sending flush command...")
        await tts.flush()

        # Wait for finalization
        await asyncio.sleep(2)

        # Check for audio
        audio_chunks = []
        while True:
            audio = await tts.get_audio()
            if audio is None:
                break
            audio_chunks.append(audio)

        if audio_chunks:
            logger.info(f"✓ Flush successful: received {len(audio_chunks)} chunks")
            return True
        else:
            logger.error("✗ No audio received after flush")
            return False

    except Exception as e:
        logger.error(f"✗ Flush test failed: {e}")
        return False


async def test_clear_command(tts: DeepgramTTSService) -> bool:
    """
    Test 5: Clear command (barge-in).

    Simulates user interruption by clearing audio queue mid-generation.
    """
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Clear Command (Barge-In)")
    logger.info("=" * 70)

    try:
        # Send a long text
        long_text = (
            "This is a very long sentence that will take some time to synthesize. "
            "We're going to interrupt it with a clear command to simulate barge-in. "
            "This tests the system's ability to handle user interruptions gracefully."
        )

        logger.info("Sending long text...")
        await tts.send_text(long_text)

        # Wait a moment for audio to start generating
        await asyncio.sleep(0.5)

        # Check initial audio
        initial_chunks = []
        for _ in range(3):  # Get first few chunks
            audio = await tts.get_audio()
            if audio:
                initial_chunks.append(audio)

        logger.info(f"Received {len(initial_chunks)} initial chunks")

        # Send clear command (barge-in)
        logger.info("Sending CLEAR command (simulating barge-in)...")
        await tts.clear()

        # Wait a moment
        await asyncio.sleep(0.5)

        # Check that queue was cleared
        remaining = 0
        while True:
            audio = await tts.get_audio()
            if audio is None:
                break
            remaining += 1

        logger.info(f"Audio queue after clear: {remaining} chunks remaining")

        # Send new text after barge-in
        logger.info("Sending new text after barge-in...")
        await tts.send_text("User interrupted. New response.")
        await tts.flush()
        await asyncio.sleep(1)

        # Check for new audio
        new_chunks = []
        while True:
            audio = await tts.get_audio()
            if audio is None:
                break
            new_chunks.append(audio)

        if new_chunks:
            logger.info(
                f"✓ Clear/barge-in successful: "
                f"cleared queue and generated {len(new_chunks)} new chunks"
            )
            return True
        else:
            logger.error("✗ No new audio after clear")
            return False

    except Exception as e:
        logger.error(f"✗ Clear test failed: {e}")
        return False


async def test_performance_metrics(tts: DeepgramTTSService) -> bool:
    """
    Test 6: Performance metrics.

    Measures time-to-first-byte and overall latency.
    """
    logger.info("\n" + "=" * 70)
    logger.info("TEST 6: Performance Metrics")
    logger.info("=" * 70)

    try:
        test_text = "This is a performance test."

        # Measure time to first byte
        start_time = time.time()

        logger.info("Sending text and measuring latency...")
        await tts.send_text(test_text)

        # Wait for first audio chunk
        first_byte_time = None
        for i in range(50):  # Wait up to 5 seconds
            audio = await tts.get_audio()
            if audio:
                first_byte_time = time.time()
                break
            await asyncio.sleep(0.1)

        if first_byte_time:
            ttfb = (first_byte_time - start_time) * 1000  # Convert to ms
            logger.info(f"✓ Time to First Byte: {ttfb:.2f}ms")

            # Flush and measure total time
            await tts.flush()
            await asyncio.sleep(1)

            # Collect remaining audio
            chunk_count = 1  # Already got first chunk
            while True:
                audio = await tts.get_audio()
                if audio is None:
                    break
                chunk_count += 1

            total_time = (time.time() - start_time) * 1000
            logger.info(f"✓ Total synthesis time: {total_time:.2f}ms")
            logger.info(f"✓ Total chunks received: {chunk_count}")

            return True
        else:
            logger.error("✗ No audio received within timeout")
            return False

    except Exception as e:
        logger.error(f"✗ Performance test failed: {e}")
        return False


async def test_disconnect(tts: DeepgramTTSService) -> bool:
    """
    Test 7: Clean disconnection.

    Verifies graceful connection closure and resource cleanup.
    """
    logger.info("\n" + "=" * 70)
    logger.info("TEST 7: Disconnection")
    logger.info("=" * 70)

    try:
        await tts.disconnect()

        if not tts.is_connected:
            logger.info("✓ Disconnected successfully")
            return True
        else:
            logger.error("✗ Disconnection failed: is_connected is still True")
            return False

    except Exception as e:
        logger.error(f"✗ Disconnection failed: {e}")
        return False


async def main():
    """Run all TTS tests."""
    logger.info("\n" + "=" * 70)
    logger.info("DEEPGRAM TTS SERVICE TEST SUITE")
    logger.info("=" * 70)

    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        logger.error("❌ DEEPGRAM_API_KEY not found in environment")
        sys.exit(1)

    logger.info(f"API Key: {api_key[:20]}...")

    # Get TTS configuration
    model = os.getenv("DEEPGRAM_TTS_MODEL", "aura-2-asteria-en")
    encoding = os.getenv("DEEPGRAM_TTS_ENCODING", "mulaw")
    sample_rate = int(os.getenv("DEEPGRAM_TTS_SAMPLE_RATE", "8000"))

    logger.info(f"Model: {model}")
    logger.info(f"Encoding: {encoding}")
    logger.info(f"Sample Rate: {sample_rate} Hz")

    # Initialize TTS service
    tts = DeepgramTTSService(
        api_key=api_key,
        model=model,
        encoding=encoding,
        sample_rate=sample_rate,
    )

    # Run tests
    results = {}

    results["connection"] = await test_connection(tts)

    if results["connection"]:
        results["text_synthesis"] = await test_text_synthesis(tts)
        results["streaming"] = await test_streaming_synthesis(tts)
        results["flush"] = await test_flush_command(tts)
        results["clear"] = await test_clear_command(tts)
        results["performance"] = await test_performance_metrics(tts)
        results["disconnect"] = await test_disconnect(tts)
    else:
        logger.error("Skipping remaining tests due to connection failure")
        results.update(
            {
                "text_synthesis": False,
                "streaming": False,
                "flush": False,
                "clear": False,
                "performance": False,
                "disconnect": False,
            }
        )

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{test_name.upper():.<50} {status}")

    logger.info("=" * 70)
    logger.info(f"TOTAL: {passed}/{total} tests passed")
    logger.info("=" * 70)

    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
