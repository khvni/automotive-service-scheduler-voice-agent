#!/usr/bin/env python3
"""
Simple script to test outbound Twilio call WITHOUT needing the full server.
This proves your Twilio setup works.
"""

import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Get Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
YOUR_TEST_NUMBER = os.getenv("YOUR_TEST_NUMBER")
BASE_URL = os.getenv("BASE_URL")

print("=" * 80)
print("TWILIO OUTBOUND CALL TEST")
print("=" * 80)
print()

# Validate environment variables
print("📋 Checking configuration...")
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, YOUR_TEST_NUMBER]):
    print("❌ Missing required environment variables!")
    print(f"  TWILIO_ACCOUNT_SID: {'✓' if TWILIO_ACCOUNT_SID else '✗'}")
    print(f"  TWILIO_AUTH_TOKEN: {'✓' if TWILIO_AUTH_TOKEN else '✗'}")
    print(f"  TWILIO_PHONE_NUMBER: {'✓' if TWILIO_PHONE_NUMBER else '✗'}")
    print(f"  YOUR_TEST_NUMBER: {'✓' if YOUR_TEST_NUMBER else '✗'}")
    exit(1)

print(f"✓ TWILIO_ACCOUNT_SID: {TWILIO_ACCOUNT_SID}")
print(f"✓ TWILIO_AUTH_TOKEN: {TWILIO_AUTH_TOKEN[:10]}...")
print(f"✓ From Number: {TWILIO_PHONE_NUMBER}")
print(f"✓ To Number: {YOUR_TEST_NUMBER}")
print(f"✓ BASE_URL: {BASE_URL}")
print()

# Initialize Twilio client
try:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("✓ Twilio client initialized successfully")
    print()
except Exception as e:
    print(f"❌ Failed to initialize Twilio client: {e}")
    exit(1)

# Show what we're about to do
print("=" * 80)
print("READY TO MAKE TEST CALL")
print("=" * 80)
print()
print(f"This will call: {YOUR_TEST_NUMBER}")
print(f"From: {TWILIO_PHONE_NUMBER}")
print()
print("⚠️  NOTE: Since your server isn't running, the call will connect")
print("   but you'll hear an error message or nothing. That's OK!")
print("   This test just proves Twilio API works.")
print()

# Auto-confirm for automated testing
print("⚠️  Auto-proceeding with call (no confirmation needed in automation)")

print()
print("🚀 Initiating call...")

try:
    # Make the call with a simple TwiML webhook
    # Since server isn't running, we'll use Twilio's TwiML bins for testing
    call = client.calls.create(
        to=YOUR_TEST_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
        url="http://twimlets.com/message?Message%5B0%5D=This%20is%20a%20test%20call%20from%20your%20automotive%20voice%20POC.%20Your%20Twilio%20integration%20is%20working!",
        method="POST"
    )

    print("✓ Call initiated successfully!")
    print()
    print(f"Call SID: {call.sid}")
    print(f"Status: {call.status}")
    print(f"To: {call.to}")
    print(f"From: {call.from_}")
    print()
    print("📞 YOUR PHONE SHOULD RING SHORTLY!")
    print()
    print("When you answer, you'll hear:")
    print('"This is a test call from your automotive voice POC."')
    print('"Your Twilio integration is working!"')
    print()
    print("=" * 80)
    print("SUCCESS! Twilio API is working correctly.")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Fix the server startup issues (Python version/dependencies)")
    print("  2. Configure Twilio webhook to point to your ngrok URL")
    print("  3. Run the full demo with server running")

except Exception as e:
    print(f"❌ Call failed: {e}")
    print()
    print("Common issues:")
    print("  - Invalid Twilio credentials")
    print("  - Phone number not verified (trial accounts)")
    print("  - Insufficient Twilio balance")
    print("  - Invalid phone number format (must be E.164: +1XXXXXXXXXX)")
