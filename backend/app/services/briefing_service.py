"""Morning briefing service — generates a daily summary for Harman.

Runs at 6am SGT via APScheduler. Compiles unread emails and
produces a concise morning briefing using Claude.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

from app.config import settings

logger = logging.getLogger("tuesday.briefing")

SGT = timezone(timedelta(hours=8))
_BRIEFINGS_DIR = Path(__file__).resolve().parents[1] / "briefings"


def _briefings_dir() -> Path:
    _BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    return _BRIEFINGS_DIR


def _today_path() -> Path:
    today = datetime.now(SGT).strftime("%Y-%m-%d")
    return _briefings_dir() / f"{today}.json"


async def get_today_briefing() -> dict | None:
    """Return today's briefing if it exists."""
    path = _today_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


async def generate_briefing() -> dict:
    """Generate today's morning briefing.

    Fetches unread emails, checks decision follow-ups,
    then asks Claude to synthesize a briefing.
    """
    logger.info("Generating morning briefing...")

    # Gather data
    sections = []

    # 1. Unread emails
    try:
        from app.services import gmail_service
        email_summary = await gmail_service.get_messages({
            "unread_only": True,
            "max_results": 20,
        })
        if "not connected" not in email_summary.lower() and "not configured" not in email_summary.lower():
            sections.append(f"## Unread Emails\n{email_summary}")
    except Exception as e:
        logger.warning(f"Could not fetch emails for briefing: {e}")

    # 2. Decision follow-ups
    try:
        from app.tools.executor import _check_followups
        followups = await _check_followups({"days_ahead": 3})
        if "No follow-ups" not in followups:
            sections.append(f"## Follow-ups Due\n{followups}")
    except Exception as e:
        logger.warning(f"Could not check follow-ups for briefing: {e}")

    # 3. Reminders
    try:
        from app.tools.executor import _list_reminders
        reminders = await _list_reminders({"include_done": False})
        if "No active reminders" not in reminders and "No reminders" not in reminders:
            sections.append(f"## Active Reminders\n{reminders}")
    except Exception as e:
        logger.warning(f"Could not check reminders for briefing: {e}")

    if not sections:
        briefing_content = "No unread emails, no follow-ups, and no reminders. Clear morning."
    else:
        # Ask Claude to synthesize — with full personality context
        from app.services.claude_service import get_condensed_system_prompt
        data_block = "\n\n".join(sections)
        prompt = (
            f"It's morning in Singapore. "
            f"Compile this data into a brief, conversational morning briefing for Harman. "
            f"Highlight anything urgent. Keep it under 200 words. "
            f"Write for speech — no markdown, no bullet points, no URLs.\n\n{data_block}"
        )

        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await client.messages.create(
                model=settings.model,
                max_tokens=1024,
                system=get_condensed_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )
            briefing_content = response.content[0].text
        except Exception as e:
            logger.error(f"Claude briefing generation failed: {e}")
            briefing_content = f"Could not generate briefing: {e}"

    # Save
    now = datetime.now(SGT)
    briefing = {
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "content": briefing_content,
        "sections_count": len(sections),
    }

    path = _today_path()
    path.write_text(json.dumps(briefing, indent=2))
    logger.info(f"Morning briefing saved: {path.name}")

    return briefing
