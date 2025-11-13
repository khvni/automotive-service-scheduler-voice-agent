"""
Application configuration using pydantic-settings.
"""

import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> str:
    """Find .env file by checking multiple locations."""
    # Try relative to this file (server/app/config.py)
    current_dir = Path(__file__).parent
    candidates = [
        current_dir / ".env",  # server/app/.env
        current_dir.parent / ".env",  # server/.env
        current_dir.parent.parent / ".env",  # project root/.env
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Default to project root
    return str(current_dir.parent.parent / ".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = ""  # Must be set in .env file

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SESSION_TTL: int = 3600  # 1 hour

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WEBHOOK_URL: str = ""
    BASE_URL: str = (
        "https://your-domain.ngrok.io"  # Public URL for webhooks (ngrok during development)
    )

    # Deepgram STT
    DEEPGRAM_API_KEY: str = ""
    DEEPGRAM_MODEL: str = "nova-2-phonecall"  # Optimized for phone audio
    DEEPGRAM_LANGUAGE: str = "en"
    DEEPGRAM_ENCODING: str = "mulaw"  # Twilio audio encoding
    DEEPGRAM_SAMPLE_RATE: int = 8000  # Phone quality
    DEEPGRAM_CHANNELS: int = 1
    DEEPGRAM_INTERIM_RESULTS: bool = True  # Enable for barge-in detection
    DEEPGRAM_SMART_FORMAT: bool = True
    DEEPGRAM_ENDPOINTING: int = 300  # ms
    DEEPGRAM_UTTERANCE_END_MS: int = 1000  # ms

    # Deepgram TTS
    DEEPGRAM_TTS_MODEL: str = "aura-2-asteria-en"  # Natural female voice
    DEEPGRAM_TTS_ENCODING: str = "mulaw"  # Twilio audio encoding
    DEEPGRAM_TTS_SAMPLE_RATE: int = 8000  # Phone quality

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"  # Standard Chat Completions API (not Realtime)
    OPENAI_TEMPERATURE: float = 0.8  # Sampling temperature for responses
    OPENAI_MAX_TOKENS: int = 1000  # Maximum tokens per response
    OPENAI_VOICE: str = "alloy"  # Voice for Realtime API (not used with standard API)

    # ElevenLabs (optional)
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""

    # Google Calendar (OAuth2)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    CALENDAR_TIMEZONE: str = "America/New_York"

    # VIN API
    NHTSA_API_URL: str = "https://vpic.nhtsa.dot.gov/api"

    # Business Logic
    SERVICE_CENTER_NAME: str = "Premium Auto Service"
    SERVICE_CENTER_HOURS: str = "Monday-Friday 8AM-6PM, Saturday 9AM-4PM"
    DEFAULT_APPOINTMENT_DURATION: int = 60  # minutes

    # Worker Configuration
    REMINDER_CRON_SCHEDULE: str = "0 9 * * *"  # Daily at 9 AM
    REMINDER_DAYS_BEFORE: int = 1  # Remind 1 day before appointment
    SERVER_API_URL: str = "http://localhost:8000/api/v1"

    # POC Safety Feature: Only call this number during testing
    YOUR_TEST_NUMBER: str = "+1234567890"  # Set to your real number for testing


settings = Settings()
