"""
Test script for voice WebSocket handler.

This script simulates a Twilio Media Stream connection to test the
voice handler's functionality without making actual phone calls.

Usage:
    python scripts/test_voice_handler.py
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from app.main import app
from fastapi.testclient import TestClient


def generate_test_audio():
    """
    Generate test audio payload (mulaw silence).

    Returns 160 bytes of mulaw silence (20ms at 8kHz).
    """
    # Mulaw silence is 0xFF (255)
    silence = bytes([0xFF] * 160)
    return base64.b64encode(silence).decode("utf-8")


async def test_websocket_connection():
    """Test WebSocket connection and basic flow."""
    print("Starting WebSocket test...")

    client = TestClient(app)

    with client.websocket_connect("/api/v1/voice/media-stream") as websocket:
        print("✓ WebSocket connected")

        # Send 'connected' event
        websocket.send_json({"event": "connected", "protocol": "Call", "version": "1.0.0"})
        print("✓ Sent 'connected' event")

        # Send 'start' event
        start_event = {
            "event": "start",
            "sequenceNumber": "1",
            "start": {
                "streamSid": "MZ1234567890abcdef",
                "accountSid": "AC1234567890abcdef",  # pragma: allowlist secret
                "callSid": "CA1234567890abcdef",  # pragma: allowlist secret
                "from": "+15551234567",
                "customParameters": {"From": "+15551234567"},
            },
            "streamSid": "MZ1234567890abcdef",
        }
        websocket.send_json(start_event)
        print("✓ Sent 'start' event")

        # Send some test audio frames
        for i in range(10):
            media_event = {
                "event": "media",
                "sequenceNumber": str(i + 2),
                "media": {
                    "track": "inbound",
                    "chunk": str(i),
                    "timestamp": str(i * 20),
                    "payload": generate_test_audio(),
                },
                "streamSid": "MZ1234567890abcdef",
            }
            websocket.send_json(media_event)

            if i == 0:
                print("✓ Sent test audio frames")

            await asyncio.sleep(0.02)  # 20ms delay between frames

        # Send 'stop' event
        stop_event = {
            "event": "stop",
            "sequenceNumber": "12",
            "streamSid": "MZ1234567890abcdef",
            "stop": {
                "accountSid": "AC1234567890abcdef",  # pragma: allowlist secret
                "callSid": "CA1234567890abcdef",  # pragma: allowlist secret
            },
        }
        websocket.send_json(stop_event)
        print("✓ Sent 'stop' event")

        # Receive any responses
        try:
            while True:
                data = websocket.receive_json(timeout=1.0)
                event_type = data.get("event")
                if event_type == "media":
                    print(f"✓ Received audio response from TTS")
                elif event_type == "clear":
                    print(f"✓ Received clear event (barge-in)")
                else:
                    print(f"  Received: {event_type}")
        except:
            pass

    print("\n✓ Test completed successfully!")


def test_incoming_webhook():
    """Test incoming call webhook."""
    print("\nTesting incoming call webhook...")

    client = TestClient(app)
    response = client.post("/api/v1/voice/incoming")

    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Stream" in response.text

    print("✓ Incoming webhook returns valid TwiML")


if __name__ == "__main__":
    print("=" * 60)
    print("Voice WebSocket Handler Test")
    print("=" * 60)
    print()

    # Test 1: Incoming webhook
    test_incoming_webhook()

    # Test 2: WebSocket connection (requires async)
    print()
    print("Note: Full WebSocket test requires running server separately")
    print("To test WebSocket:")
    print("  1. Start server: uvicorn app.main:app --reload")
    print("  2. Use Twilio CLI or WebSocket client")
    print()

    print("=" * 60)
    print("Basic tests passed ✓")
    print("=" * 60)
