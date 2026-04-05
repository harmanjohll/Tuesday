"""APScheduler setup for Tuesday's background tasks.

Currently runs:
- Morning briefing at 6:00 AM SGT (22:00 UTC previous day)
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("tuesday.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _run_briefing():
    """Wrapper to run briefing generation."""
    try:
        from app.services.briefing_service import generate_briefing
        await generate_briefing()
    except Exception as e:
        logger.error(f"Scheduled briefing failed: {e}")


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler

    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()

    # Morning briefing: 6:00 AM SGT = 22:00 UTC (previous day)
    _scheduler.add_job(
        _run_briefing,
        trigger=CronTrigger(hour=22, minute=0),  # 22:00 UTC = 6:00 AM SGT
        id="morning_briefing",
        name="Morning briefing for Harman",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started — morning briefing at 6:00 AM SGT")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
