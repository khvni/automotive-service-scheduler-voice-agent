#!/usr/bin/env python3
"""
Auto-update Twilio Phone Number Webhook

This script automatically updates the Twilio phone number's voice webhook URL
to point to the current ngrok tunnel. This solves the problem of expired ngrok
URLs breaking inbound calls.

Usage:
    python scripts/update_twilio_webhook.py <ngrok_url>

Example:
    python scripts/update_twilio_webhook.py https://abc123.ngrok.io
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from twilio.rest import Client
from app.config import settings


def update_webhook(ngrok_url: str) -> None:
    """
    Update Twilio phone number webhook to point to ngrok URL.

    Args:
        ngrok_url: The ngrok public URL (e.g., https://abc123.ngrok.io)
    """
    # Initialize Twilio client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    # Construct webhook URLs
    voice_url = f"{ngrok_url}/api/v1/voice/incoming"
    status_callback_url = f"{ngrok_url}/api/v1/webhooks/status"

    print(f"📞 Updating Twilio webhook configuration...")
    print(f"   Phone Number: {settings.TWILIO_PHONE_NUMBER}")
    print(f"   Voice URL: {voice_url}")
    print(f"   Status Callback: {status_callback_url}")

    try:
        # Get all phone numbers for this account
        phone_numbers = client.incoming_phone_numbers.list(
            phone_number=settings.TWILIO_PHONE_NUMBER
        )

        if not phone_numbers:
            print(f"❌ Error: Phone number {settings.TWILIO_PHONE_NUMBER} not found in account")
            print(f"   Available numbers:")
            all_numbers = client.incoming_phone_numbers.list(limit=10)
            for number in all_numbers:
                print(f"   - {number.phone_number}")
            sys.exit(1)

        # Update the phone number configuration
        phone_number = phone_numbers[0]
        phone_number.update(
            voice_url=voice_url,
            voice_method="POST",
            status_callback=status_callback_url,
            status_callback_method="POST",
        )

        print(f"✅ Webhook updated successfully!")
        print(f"   Inbound calls to {settings.TWILIO_PHONE_NUMBER} will now route to:")
        print(f"   {voice_url}")

    except Exception as e:
        print(f"❌ Error updating Twilio webhook: {e}")
        print(f"\n💡 Troubleshooting:")
        print(f"   1. Check your Twilio credentials in .env")
        print(f"   2. Verify phone number {settings.TWILIO_PHONE_NUMBER} exists in your account")
        print(f"   3. Ensure you have permission to update phone number settings")
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/update_twilio_webhook.py <ngrok_url>")
        print("Example: python scripts/update_twilio_webhook.py https://abc123.ngrok.io")
        sys.exit(1)

    ngrok_url = sys.argv[1].rstrip("/")  # Remove trailing slash if present

    # Validate URL format
    if not ngrok_url.startswith("http"):
        print(f"❌ Error: Invalid URL format: {ngrok_url}")
        print(f"   URL must start with http:// or https://")
        sys.exit(1)

    update_webhook(ngrok_url)


if __name__ == "__main__":
    main()
