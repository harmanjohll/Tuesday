"""Activity tracker — records what happened while Harman was away.

Accumulates events (agent starts, completions, pipeline steps) so the
frontend can show a summary when the tab regains focus.

Events auto-expire after 30 minutes.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone, timedelta

_lock = threading.Lock()
_events: list[dict] = []
_last_seen: str = datetime.now(timezone.utc).isoformat()

EXPIRY_MINUTES = 30


def record_event(
    event_type: str,
    agent: str = "",
    message: str = "",
    progress: float | None = None,
) -> None:
    """Record an activity event."""
    with _lock:
        _purge_expired()
        _events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "agent": agent,
            "message": message,
            "progress": progress,
        })


def get_events_since(timestamp: str) -> list[dict]:
    """Return events after the given ISO timestamp."""
    with _lock:
        _purge_expired()
        return [e for e in _events if e["timestamp"] > timestamp]


def get_pending_summary() -> str | None:
    """Brief text summary of events since last seen. None if nothing happened."""
    events = get_events_since(_last_seen)
    if not events:
        return None

    parts: list[str] = []
    for e in events:
        agent = e["agent"]
        msg = e["message"]
        if agent and msg:
            parts.append(f"{agent}: {msg}")
        elif msg:
            parts.append(msg)

    if not parts:
        return None

    # Deduplicate and limit
    seen = set()
    unique: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return " | ".join(unique[:5])


def mark_seen() -> None:
    """Update last-seen timestamp (called when tab becomes visible)."""
    global _last_seen
    _last_seen = datetime.now(timezone.utc).isoformat()


def get_last_seen() -> str:
    return _last_seen


def _purge_expired() -> None:
    """Remove events older than EXPIRY_MINUTES. Must hold _lock."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=EXPIRY_MINUTES)).isoformat()
    _events[:] = [e for e in _events if e["timestamp"] > cutoff]
