"""Activity event log -- tracks events that happen while the user is away."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.config import settings

logger = logging.getLogger("tuesday.activity")

SGT = timezone(timedelta(hours=8))

_LOG_FILE: Path = settings.logs_dir / "activity.jsonl"

# In-memory cache (also persisted to JSONL)
_events: list[dict] = []


def _load_events() -> None:
    """Load events from disk on first access."""
    global _events
    if _events:
        return
    if _LOG_FILE.exists():
        try:
            for line in _LOG_FILE.read_text().strip().splitlines():
                if line.strip():
                    _events.append(json.loads(line))
        except (json.JSONDecodeError, IOError):
            logger.warning("Could not load activity log, starting fresh")
            _events = []


def log_event(
    event_type: str,
    title: str,
    detail: str = "",
    agent_name: str = "",
) -> None:
    """Log an activity event. Types: agent_complete, error, briefing, scheduled, reminder."""
    _load_events()

    event = {
        "event_type": event_type,
        "title": title,
        "detail": detail,
        "agent_name": agent_name,
        "timestamp": datetime.now(SGT).isoformat(),
    }
    _events.append(event)

    # Persist to JSONL
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a") as f:
            f.write(json.dumps(event) + "\n")
    except IOError as e:
        logger.warning(f"Could not write activity event: {e}")

    # Keep only last 7 days in memory
    _prune_old_events()

    logger.info(f"Activity: [{event_type}] {title}")


def get_events_since(iso_ts: str) -> list[dict]:
    """Return all events since the given ISO timestamp."""
    _load_events()

    try:
        cutoff = datetime.fromisoformat(iso_ts)
    except ValueError:
        return _events[-20:]  # Fallback: return recent events

    return [
        e for e in _events
        if datetime.fromisoformat(e["timestamp"]) > cutoff
    ]


def _prune_old_events() -> None:
    """Remove events older than 7 days from in-memory cache."""
    global _events
    cutoff = datetime.now(SGT) - timedelta(days=7)
    _events = [
        e for e in _events
        if datetime.fromisoformat(e["timestamp"]) > cutoff
    ]
