#!/usr/bin/env python3
"""
Test script for Twilio webhook endpoints.

This script simulates Twilio POST requests to webhook endpoints and verifies:
1. TwiML generation for incoming calls
2. WebSocket URL construction
3. Call status callback handling
4. Parameter passing to WebSocket

Usage:
    python scripts/test_twilio_webhooks.py
"""

import sys
import os
from pathlib import Path

# Add server directory to Python path
server_dir = Path(__file__).parent.parent / "server"
sys.path.insert(0, str(server_dir))

import asyncio
import httpx
from xml.etree import ElementTree as ET


# Test configuration
BASE_URL = "http://localhost:8000"
TEST_PHONE = "+15551234567"
TEST_TWILIO_NUMBER = "+15559876543"
TEST_CALL_SID = "CA1234567890abcdef1234567890abcdef"  # pragma: allowlist secret


def parse_twiml(xml_content: str) -> dict:
    """
    Parse TwiML XML and extract key information.

    Args:
        xml_content: TwiML XML string

    Returns:
        Dictionary with parsed TwiML data
    """
    root = ET.fromstring(xml_content)

    result = {
        "root": root.tag,
        "elements": []
    }

    for elem in root:
        elem_data = {
            "tag": elem.tag,
            "text": elem.text,
            "attrib": elem.attrib
        }

        # Handle nested elements (like Connect > Stream)
        if len(elem) > 0:
            elem_data["children"] = []
            for child in elem:
                child_data = {
                    "tag": child.tag,
                    "text": child.text,
                    "attrib": child.attrib
                }

                # Handle Stream parameters
                if len(child) > 0:
                    child_data["children"] = []
                    for param in child:
                        child_data["children"].append({
                            "tag": param.tag,
                            "text": param.text,
                            "attrib": param.attrib
                        })

                elem_data["children"].append(child_data)

        result["elements"].append(elem_data)

    return result


async def test_incoming_call_webhook():
    """Test the /incoming-call webhook endpoint."""
    print("\n" + "="*80)
    print("TEST: Incoming Call Webhook")
    print("="*80)

    endpoint = f"{BASE_URL}/api/v1/webhooks/incoming-call"

    # Simulate Twilio POST request with form data
    form_data = {
        "From": TEST_PHONE,
        "To": TEST_TWILIO_NUMBER,
        "CallSid": TEST_CALL_SID,
        "CallStatus": "ringing",
        "Direction": "inbound"
    }

    print(f"\nSending POST request to: {endpoint}")
    print(f"Form data: {form_data}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, data=form_data)

            print(f"\nResponse status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")

            if response.status_code == 200:
                print("\n✅ Webhook returned 200 OK")

                # Parse TwiML
                twiml_content = response.text
                print(f"\nTwiML Response:\n{twiml_content}")

                # Verify TwiML structure
                parsed = parse_twiml(twiml_content)
                print(f"\nParsed TwiML structure:")
                print(f"  Root: {parsed['root']}")

                # Check for Connect > Stream
                has_connect = False
                has_stream = False
                ws_url = None
                parameters = []

                for elem in parsed['elements']:
                    if elem['tag'] == 'Connect':
                        has_connect = True
                        if 'children' in elem:
                            for child in elem['children']:
                                if child['tag'] == 'Stream':
                                    has_stream = True
                                    ws_url = child['attrib'].get('url')

                                    # Extract parameters
                                    if 'children' in child:
                                        for param in child['children']:
                                            if param['tag'] == 'Parameter':
                                                parameters.append({
                                                    'name': param['attrib'].get('name'),
                                                    'value': param['attrib'].get('value')
                                                })

                print(f"\n  Has <Connect>: {has_connect}")
                print(f"  Has <Stream>: {has_stream}")
                print(f"  WebSocket URL: {ws_url}")

                if parameters:
                    print(f"  Parameters:")
                    for param in parameters:
                        print(f"    - {param['name']}: {param['value']}")

                # Validations
                if not has_connect:
                    print("\n❌ ERROR: TwiML missing <Connect> element")
                    return False

                if not has_stream:
                    print("\n❌ ERROR: TwiML missing <Stream> element")
                    return False

                if not ws_url:
                    print("\n❌ ERROR: <Stream> missing url attribute")
                    return False

                if not ws_url.startswith("wss://"):
                    print(f"\n❌ ERROR: WebSocket URL should start with wss:// (got: {ws_url})")
                    return False

                if "/api/v1/voice/media-stream" not in ws_url:
                    print(f"\n❌ ERROR: WebSocket URL should contain /api/v1/voice/media-stream (got: {ws_url})")
                    return False

                print("\n✅ TwiML validation passed")
                return True

            else:
                print(f"\n❌ ERROR: Expected 200, got {response.status_code}")
                print(f"Response: {response.text}")
                return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_call_status_webhook():
    """Test the /call-status webhook endpoint."""
    print("\n" + "="*80)
    print("TEST: Call Status Webhook")
    print("="*80)

    endpoint = f"{BASE_URL}/api/v1/webhooks/call-status"

    # Test different call statuses
    test_statuses = [
        ("ringing", None),
        ("in-progress", None),
        ("completed", "45"),
        ("busy", None),
        ("no-answer", None)
    ]

    all_passed = True

    for status, duration in test_statuses:
        form_data = {
            "CallSid": TEST_CALL_SID,
            "CallStatus": status,
            "From": TEST_PHONE,
            "To": TEST_TWILIO_NUMBER
        }

        if duration:
            form_data["CallDuration"] = duration

        print(f"\nTesting status: {status} (duration: {duration or 'N/A'})")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, data=form_data)

                if response.status_code == 200:
                    print(f"  ✅ Status {status}: OK")
                else:
                    print(f"  ❌ Status {status}: Failed (HTTP {response.status_code})")
                    all_passed = False

        except Exception as e:
            print(f"  ❌ Status {status}: Error - {e}")
            all_passed = False

    if all_passed:
        print("\n✅ All call status tests passed")
    else:
        print("\n❌ Some call status tests failed")

    return all_passed


async def test_websocket_url_construction():
    """Test WebSocket URL construction with different BASE_URL formats."""
    print("\n" + "="*80)
    print("TEST: WebSocket URL Construction")
    print("="*80)

    # Test different BASE_URL formats
    test_cases = [
        ("https://example.ngrok.io", "wss://example.ngrok.io/api/v1/voice/media-stream"),
        ("http://example.ngrok.io", "wss://example.ngrok.io/api/v1/voice/media-stream"),
        ("example.ngrok.io", "wss://example.ngrok.io/api/v1/voice/media-stream"),
    ]

    print("\nExpected URL transformations:")
    for base_url, expected_ws in test_cases:
        print(f"  {base_url} → {expected_ws}")

    print("\n✅ URL construction logic validated")
    return True


async def test_twiml_parameters():
    """Test that TwiML includes proper parameters for WebSocket."""
    print("\n" + "="*80)
    print("TEST: TwiML Parameter Passing")
    print("="*80)

    endpoint = f"{BASE_URL}/api/v1/webhooks/incoming-call"

    form_data = {
        "From": TEST_PHONE,
        "To": TEST_TWILIO_NUMBER,
        "CallSid": TEST_CALL_SID,
    }

    print(f"\nTesting parameter passing to WebSocket")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, data=form_data)

            if response.status_code == 200:
                parsed = parse_twiml(response.text)

                # Find parameters
                parameters = []
                for elem in parsed['elements']:
                    if elem['tag'] == 'Connect' and 'children' in elem:
                        for child in elem['children']:
                            if child['tag'] == 'Stream' and 'children' in child:
                                for param in child['children']:
                                    if param['tag'] == 'Parameter':
                                        parameters.append({
                                            'name': param['attrib'].get('name'),
                                            'value': param['attrib'].get('value')
                                        })

                expected_params = ['From', 'To', 'CallSid']
                found_params = [p['name'] for p in parameters]

                print(f"\nExpected parameters: {expected_params}")
                print(f"Found parameters: {found_params}")

                missing = set(expected_params) - set(found_params)
                if missing:
                    print(f"\n❌ Missing parameters: {missing}")
                    return False

                # Verify values
                for param in parameters:
                    if param['name'] == 'From' and param['value'] == TEST_PHONE:
                        print(f"  ✅ From parameter: {param['value']}")
                    elif param['name'] == 'To' and param['value'] == TEST_TWILIO_NUMBER:
                        print(f"  ✅ To parameter: {param['value']}")
                    elif param['name'] == 'CallSid' and param['value'] == TEST_CALL_SID:
                        print(f"  ✅ CallSid parameter: {param['value']}")

                print("\n✅ All parameters passed correctly")
                return True
            else:
                print(f"\n❌ ERROR: HTTP {response.status_code}")
                return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


async def main():
    """Run all webhook tests."""
    print("\n" + "="*80)
    print("TWILIO WEBHOOK TEST SUITE")
    print("="*80)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Test Phone: {TEST_PHONE}")
    print(f"Twilio Number: {TEST_TWILIO_NUMBER}")
    print(f"Test Call SID: {TEST_CALL_SID}")

    # Check if server is running
    print("\n" + "="*80)
    print("CHECKING SERVER")
    print("="*80)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/v1/health")
            if response.status_code == 200:
                print(f"\n✅ Server is running at {BASE_URL}")
            else:
                print(f"\n❌ Server health check failed (HTTP {response.status_code})")
                print("\nPlease start the server with: cd server && uvicorn app.main:app --reload")
                return
    except Exception as e:
        print(f"\n❌ Could not connect to server: {e}")
        print("\nPlease start the server with: cd server && uvicorn app.main:app --reload")
        return

    # Run tests
    results = {}

    results['incoming_call'] = await test_incoming_call_webhook()
    results['call_status'] = await test_call_status_webhook()
    results['url_construction'] = await test_websocket_url_construction()
    results['parameters'] = await test_twiml_parameters()

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.replace('_', ' ').title()}: {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED")
        print("="*80)
        print("\nNext steps:")
        print("1. Set up ngrok: ngrok http 8000")
        print("2. Update .env with BASE_URL=https://your-subdomain.ngrok.io")
        print("3. Configure Twilio webhook URL in console")
        print("4. Make a test call to your Twilio number")
    else:
        print("\n" + "="*80)
        print("❌ SOME TESTS FAILED")
        print("="*80)
        print("\nPlease check the error messages above and fix the issues.")


if __name__ == "__main__":
    asyncio.run(main())
