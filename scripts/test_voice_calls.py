#!/usr/bin/env python3
"""
Voice Agent Testing Script

This script allows you to test the voice agent with both inbound and outbound calls:
- Inbound: The agent receives a call (you call the Twilio number)
- Outbound: The agent calls you (initiates a call to YOUR_TEST_NUMBER)

Requirements:
- Server must be running (uvicorn)
- ngrok tunnel must be active and BASE_URL configured in .env
- Twilio account with credits
- Redis and PostgreSQL running
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from twilio.rest import Client

from app.config import settings


class VoiceAgentTester:
    """Test harness for voice agent functionality."""

    def __init__(self):
        """Initialize Twilio client."""
        # Validate configuration
        if not settings.TWILIO_ACCOUNT_SID or settings.TWILIO_ACCOUNT_SID == "":
            raise ValueError("TWILIO_ACCOUNT_SID not set in .env")
        if not settings.TWILIO_AUTH_TOKEN or settings.TWILIO_AUTH_TOKEN == "":
            raise ValueError("TWILIO_AUTH_TOKEN not set in .env")
        if not settings.TWILIO_PHONE_NUMBER or settings.TWILIO_PHONE_NUMBER == "":
            raise ValueError("TWILIO_PHONE_NUMBER not set in .env")
        if not settings.YOUR_TEST_NUMBER or settings.YOUR_TEST_NUMBER == "+1234567890":
            raise ValueError(
                "YOUR_TEST_NUMBER not properly configured in .env (set to your real number)"
            )

        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.to_number = settings.YOUR_TEST_NUMBER
        self.base_url = settings.BASE_URL

        # Ensure BASE_URL is properly formatted
        if not self.base_url.startswith("http"):
            self.base_url = f"https://{self.base_url}"
        if self.base_url.endswith("/"):
            self.base_url = self.base_url[:-1]

        print(f"✓ Twilio client initialized")
        print(f"  From: {self.from_number}")
        print(f"  To: {self.to_number}")
        print(f"  Base URL: {self.base_url}")
        print()

    def test_inbound_setup(self):
        """
        Display instructions for testing inbound calls.

        This doesn't make a call - it shows you the number to call.
        """
        print("=" * 70)
        print("INBOUND CALL TEST")
        print("=" * 70)
        print()
        print(f"To test inbound calls, simply call this number from your phone:")
        print()
        print(f"  📞  {self.from_number}")
        print()
        print("The voice agent will answer and you can interact with Sophie,")
        print("the automotive service receptionist.")
        print()
        print("What to test:")
        print("  • Appointment scheduling")
        print("  • Service inquiries")
        print("  • Customer lookup (if you're in the database)")
        print("  • Barge-in (interrupt Sophie while she's talking)")
        print()
        print("=" * 70)

    def make_outbound_call(self, call_type: str = "general"):
        """
        Initiate an outbound call to YOUR_TEST_NUMBER.

        Args:
            call_type: Type of call - 'general' or 'reminder'
        """
        print("=" * 70)
        print("OUTBOUND CALL TEST")
        print("=" * 70)
        print()

        # Choose the right webhook endpoint
        if call_type == "reminder":
            webhook_url = f"{self.base_url}/api/v1/voice/incoming-reminder"
            print("Call type: Appointment Reminder")
        else:
            webhook_url = f"{self.base_url}/api/v1/voice/incoming"
            print("Call type: Outbound Call")

        print(f"Calling {self.to_number}...")
        print(f"Webhook: {webhook_url}")
        print()

        try:
            # Initiate the call
            call = self.client.calls.create(
                to=self.to_number,
                from_=self.from_number,
                url=webhook_url,
                status_callback=f"{self.base_url}/api/v1/webhooks/status",
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                record=False,  # Set to True if you want to record for debugging
                # Pass direction parameter to voice handler
                machine_detection="Enable",  # Optional: detect voicemail
                timeout=60,  # Ring for 60 seconds before giving up
            )

            print(f"✓ Call initiated successfully!")
            print(f"  Call SID: {call.sid}")
            print(f"  Status: {call.status}")
            print()
            print("Your phone should ring in a few seconds...")
            print()
            print("What to test:")
            print("  • Answer the call and interact with Sophie")
            print("  • Try scheduling an appointment")
            print("  • Test barge-in by interrupting Sophie")
            print("  • Hang up to end the call")
            print()
            print(f"To check call status, run:")
            print(f"  python scripts/test_voice_calls.py status {call.sid}")
            print()

            return call.sid

        except Exception as e:
            print(f"✗ Failed to initiate call: {e}")
            print()
            if "authenticate" in str(e).lower():
                print("Check your Twilio credentials in .env file")
            elif "permission" in str(e).lower():
                print("Check your Twilio account has permission to make calls")
            elif "balance" in str(e).lower():
                print("Check your Twilio account has sufficient credits")
            else:
                print("Check that:")
                print("  1. Server is running (uvicorn)")
                print("  2. ngrok tunnel is active")
                print("  3. BASE_URL in .env matches ngrok URL")
            return None

    def check_call_status(self, call_sid: str):
        """
        Check the status of a call.

        Args:
            call_sid: Twilio Call SID
        """
        print("=" * 70)
        print("CALL STATUS")
        print("=" * 70)
        print()

        try:
            call = self.client.calls(call_sid).fetch()

            print(f"Call SID: {call.sid}")
            print(f"Status: {call.status}")
            print(f"Direction: {call.direction}")
            print(f"Duration: {call.duration or 'N/A'} seconds")
            print(f"From: {call.from_}")
            print(f"To: {call.to}")
            print(f"Start Time: {call.start_time or 'N/A'}")
            print(f"End Time: {call.end_time or 'N/A'}")
            print()

            # Status explanations
            status_info = {
                "queued": "Call is waiting to be initiated",
                "ringing": "Phone is ringing",
                "in-progress": "Call is active (conversation happening)",
                "completed": "Call ended successfully",
                "busy": "Recipient's line was busy",
                "failed": "Call failed to connect",
                "no-answer": "No one answered",
                "canceled": "Call was canceled",
            }

            if call.status in status_info:
                print(f"ℹ️  {status_info[call.status]}")
                print()

        except Exception as e:
            print(f"✗ Failed to fetch call status: {e}")
            print()

    def list_recent_calls(self, limit: int = 10):
        """
        List recent calls from your Twilio account.

        Args:
            limit: Number of recent calls to show
        """
        print("=" * 70)
        print(f"RECENT CALLS (last {limit})")
        print("=" * 70)
        print()

        try:
            calls = self.client.calls.list(limit=limit)

            if not calls:
                print("No calls found")
                return

            for call in calls:
                duration = f"{call.duration}s" if call.duration else "N/A"
                print(f"• {call.sid}")
                print(f"  {call.direction.upper()}: {call.from_formatted} → {call.to_formatted}")
                print(f"  Status: {call.status} | Duration: {duration}")
                print(f"  Time: {call.start_time or call.date_created}")
                print()

        except Exception as e:
            print(f"✗ Failed to list calls: {e}")
            print()


def print_usage():
    """Print usage instructions."""
    print("Voice Agent Testing Script")
    print("=" * 70)
    print()
    print("Usage:")
    print("  python scripts/test_voice_calls.py <command> [options]")
    print()
    print("Commands:")
    print("  inbound              Show instructions for testing inbound calls")
    print("  outbound             Make an outbound call (general)")
    print("  outbound-reminder    Make an outbound reminder call")
    print("  status <call_sid>    Check status of a specific call")
    print("  list [count]         List recent calls (default: 10)")
    print("  help                 Show this help message")
    print()
    print("Examples:")
    print("  python scripts/test_voice_calls.py inbound")
    print("  python scripts/test_voice_calls.py outbound")
    print("  python scripts/test_voice_calls.py status CAxxxxxxxxxx")
    print("  python scripts/test_voice_calls.py list 20")
    print()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    if command in ["help", "-h", "--help"]:
        print_usage()
        return

    try:
        tester = VoiceAgentTester()

        if command == "inbound":
            tester.test_inbound_setup()

        elif command == "outbound":
            tester.make_outbound_call("general")

        elif command == "outbound-reminder":
            tester.make_outbound_call("reminder")

        elif command == "status":
            if len(sys.argv) < 3:
                print("Error: Call SID required")
                print("Usage: python scripts/test_voice_calls.py status <call_sid>")
                sys.exit(1)
            call_sid = sys.argv[2]
            tester.check_call_status(call_sid)

        elif command == "list":
            limit = 10
            if len(sys.argv) >= 3:
                try:
                    limit = int(sys.argv[2])
                except ValueError:
                    print(f"Invalid limit: {sys.argv[2]}")
                    sys.exit(1)
            tester.list_recent_calls(limit)

        else:
            print(f"Unknown command: {command}")
            print()
            print_usage()
            sys.exit(1)

    except ValueError as e:
        print(f"Configuration Error: {e}")
        print()
        print("Make sure your .env file has these variables set correctly:")
        print("  - TWILIO_ACCOUNT_SID")
        print("  - TWILIO_AUTH_TOKEN")
        print("  - TWILIO_PHONE_NUMBER")
        print("  - YOUR_TEST_NUMBER (your real phone number)")
        print("  - BASE_URL (your ngrok URL)")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
