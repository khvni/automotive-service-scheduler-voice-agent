"""
Outbound call worker with scheduled jobs.
Handles appointment reminders and marketing calls.
"""

import logging
import sys
from pathlib import Path

# Add server directory to path to import shared models
sys.path.append(str(Path(__file__).parent.parent / "server"))

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from worker.config import settings
from worker.jobs.reminder_job import send_appointment_reminders

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Initialize and run the worker scheduler."""
    logger.info("Starting outbound call worker...")

    scheduler = AsyncIOScheduler()

    # Schedule appointment reminder job
    scheduler.add_job(
        send_appointment_reminders,
        trigger=CronTrigger.from_crontab(settings.REMINDER_CRON_SCHEDULE),
        id="appointment_reminders",
        name="Send appointment reminders",
        replace_existing=True,
    )

    # Start scheduler
    scheduler.start()
    logger.info(f"Scheduler started. Jobs: {[job.id for job in scheduler.get_jobs()]}")

    # Keep the worker running
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down worker...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
