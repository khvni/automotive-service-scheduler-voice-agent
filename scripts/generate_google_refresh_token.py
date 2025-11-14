#!/usr/bin/env python3
"""
Generate Google OAuth2 Refresh Token for Calendar API

This script helps you generate a refresh token for Google Calendar API access.

Prerequisites:
1. Google Cloud Console project with Calendar API enabled
2. OAuth 2.0 Client ID credentials created (Web application type)
3. Authorized redirect URI: http://localhost:8000
4. GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env file

Usage:
    python scripts/generate_google_refresh_token.py

    # Or automatically update .env file:
    python scripts/generate_google_refresh_token.py --update-env

The script will:
1. Load Client ID and Client Secret from .env
2. Open a browser for you to authorize the app
3. Run a local server to receive the authorization code
4. Exchange the code for tokens
5. Optionally update .env file with new refresh token
"""

import os
import re
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Google Calendar API scope
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Local redirect URI (must match Google Cloud Console setting)
# Changed to 8000 to match the FastAPI server port
REDIRECT_URI = "http://localhost:8000"


def load_env_credentials():
    """Load Google OAuth credentials from .env file."""
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        print(f"❌ Error: .env file not found at {env_path}")
        return None, None

    client_id = None
    client_secret = None

    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_CLIENT_ID="):
                client_id = line.split("=", 1)[1].strip().strip("'\"")
            elif line.startswith("GOOGLE_CLIENT_SECRET="):
                client_secret = line.split("=", 1)[1].strip().strip("'\"")

    return client_id, client_secret


def update_env_file(refresh_token):
    """Update .env file with new refresh token."""
    env_path = Path(__file__).parent.parent / ".env"

    if not env_path.exists():
        print(f"❌ Error: .env file not found at {env_path}")
        return False

    # Read existing .env content
    with open(env_path, "r") as f:
        lines = f.readlines()

    # Update or add GOOGLE_REFRESH_TOKEN
    token_found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("GOOGLE_REFRESH_TOKEN="):
            lines[i] = f"GOOGLE_REFRESH_TOKEN='{refresh_token}'\n"
            token_found = True
            break

    # If not found, add it after GOOGLE_CLIENT_SECRET
    if not token_found:
        for i, line in enumerate(lines):
            if line.strip().startswith("GOOGLE_CLIENT_SECRET="):
                lines.insert(i + 1, f"GOOGLE_REFRESH_TOKEN='{refresh_token}'\n")
                break

    # Write back to file
    with open(env_path, "w") as f:
        f.writelines(lines)

    return True


def generate_refresh_token(update_env=False):
    """Generate a refresh token using OAuth2 flow."""
    print("=" * 80)
    print("GOOGLE CALENDAR API - REFRESH TOKEN GENERATOR")
    print("=" * 80)
    print()

    # Load credentials from .env
    print("Loading credentials from .env file...")
    client_id, client_secret = load_env_credentials()

    if not client_id or not client_secret:
        print("\n❌ Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env")
        print()
        print("Add these to your .env file:")
        print("GOOGLE_CLIENT_ID='your_client_id_here'")
        print("GOOGLE_CLIENT_SECRET='your_client_secret_here'")  # pragma: allowlist secret
        print()
        sys.exit(1)

    print(f"✓ Loaded Client ID: {client_id[:20]}...")
    print(f"✓ Loaded Client Secret: {client_secret[:10]}...")
    print()

    print()
    print("=" * 80)
    print("AUTHORIZATION FLOW")
    print("=" * 80)
    print()
    print("1. A browser window will open")
    print("2. Sign in with your Google account")
    print("3. Grant calendar access permissions")
    print("4. You'll be redirected to localhost (this is normal)")
    print()

    if not update_env:
        input("Press Enter to continue...")
    else:
        print("Auto-continuing with browser authorization...")

    try:
        # Create OAuth2 flow
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            },
            scopes=SCOPES,
        )

        # Run local server to receive auth code
        creds = flow.run_local_server(port=8000, open_browser=True)

        refresh_token = creds.refresh_token

        print()
        print("=" * 80)
        print("✅ SUCCESS! Refresh token generated")
        print("=" * 80)
        print()

        if update_env:
            print("Updating .env file with new refresh token...")
            if update_env_file(refresh_token):
                print("✓ .env file updated successfully!")
                print()
                print("Your .env file now contains:")
                print(f"GOOGLE_REFRESH_TOKEN='{refresh_token}'")
            else:
                print("❌ Failed to update .env file")
                print()
                print("Manually add this to your .env file:")
                print(f"GOOGLE_REFRESH_TOKEN='{refresh_token}'")
        else:
            print("Refresh token generated (not updating .env):")
            print()
            print(f"GOOGLE_REFRESH_TOKEN='{refresh_token}'")
            print()
            print("To automatically update .env, run with --update-env flag")

        print()
        print("=" * 80)
        print()
        print("⚠️  IMPORTANT:")
        print("- Keep this refresh token secret")
        print("- Never commit it to version control")
        print("- It will remain valid until manually revoked")
        print()

        return refresh_token

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ ERROR")
        print("=" * 80)
        print()
        print(f"Failed to generate refresh token: {e}")
        print()
        print("Common issues:")
        print("1. Check that redirect URI 'http://localhost:8000' is in Google Console")
        print("2. Ensure Google Calendar API is enabled in your project")
        print("3. Verify Client ID and Client Secret are correct")
        print()
        sys.exit(1)


if __name__ == "__main__":
    # Check for --update-env flag
    update_env = "--update-env" in sys.argv
    generate_refresh_token(update_env=update_env)
