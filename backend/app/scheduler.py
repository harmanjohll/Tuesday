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


async def _run_weekly_synthesis():
    """Wrapper to run weekly metacognitive synthesis."""
    try:
        from app.services.metacognition_service import run_weekly_synthesis
        result = await run_weekly_synthesis()
        if result:
            logger.info(f"Weekly synthesis complete: {result}")
    except Exception as e:
        logger.error(f"Weekly synthesis failed: {e}")


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

    # Weekly metacognitive synthesis: Monday 6:00 AM SGT = Sunday 22:00 UTC
    from app.config import settings
    _scheduler.add_job(
        _run_weekly_synthesis,
        trigger=CronTrigger(day_of_week=settings.synthesis_day, hour=settings.synthesis_hour, minute=0),
        id="weekly_synthesis",
        name="Weekly metacognitive synthesis",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started — briefing at 6:00 AM SGT, synthesis weekly on Monday")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
