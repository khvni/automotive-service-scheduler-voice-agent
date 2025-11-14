"""Worker configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Worker settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/automotive_scheduler"  # pragma: allowlist secret  # noqa: E501

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    # Server API
    SERVER_API_URL: str = "http://localhost:8000/api/v1"

    # Scheduler settings
    REMINDER_CRON_SCHEDULE: str = "0 9 * * *"  # Run daily at 9 AM
    REMINDER_DAYS_BEFORE: int = 1  # Remind 1 day before appointment

    # POC Safety: Only call this number for testing
    YOUR_TEST_NUMBER: str = ""  # Set to your test phone number (e.g., +1234567890)


settings = WorkerSettings()
