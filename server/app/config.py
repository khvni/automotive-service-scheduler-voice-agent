"""
Application configuration using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/automotive_scheduler"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SESSION_TTL: int = 3600  # 1 hour

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WEBHOOK_URL: str = ""

    # Deepgram
    DEEPGRAM_API_KEY: str = ""
    DEEPGRAM_MODEL: str = "nova-2"
    DEEPGRAM_LANGUAGE: str = "en-US"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-realtime-preview-2024-12-17"
    OPENAI_VOICE: str = "alloy"

    # ElevenLabs (optional)
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""

    # Google Calendar
    GOOGLE_CALENDAR_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""  # Path to service account JSON

    # VIN API
    NHTSA_API_URL: str = "https://vpic.nhtsa.dot.gov/api"

    # Business Logic
    SERVICE_CENTER_NAME: str = "Premium Auto Service"
    SERVICE_CENTER_HOURS: str = "Monday-Friday 8AM-6PM, Saturday 9AM-4PM"
    DEFAULT_APPOINTMENT_DURATION: int = 60  # minutes


settings = Settings()
