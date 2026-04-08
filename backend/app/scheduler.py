"""APScheduler setup for Tuesday's background tasks.

Runs:
- Morning briefing at 6:00 AM SGT (22:00 UTC previous day)
- Weekly reflection at 9:00 PM SGT Sunday (13:00 UTC Sunday)
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


async def _run_reflection():
    """Wrapper to run weekly reflection."""
    try:
        from app.services.reflection_service import generate_weekly_reflection
        await generate_weekly_reflection()
    except Exception as e:
        logger.error(f"Scheduled reflection failed: {e}")


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

    # Weekly reflection: Sunday 9 PM SGT = 13:00 UTC Sunday
    _scheduler.add_job(
        _run_reflection,
        trigger=CronTrigger(day_of_week="sun", hour=13, minute=0),
        id="weekly_reflection",
        name="Weekly reflection synthesis",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started — briefing 6am SGT, reflection Sunday 9pm SGT")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
