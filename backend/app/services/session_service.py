"""Session persistence — file-based conversation storage."""

from __future__ import annotations

import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger("tuesday.sessions")


def _sessions_dir() -> Path:
    d = settings.sessions_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(session_id: str) -> Path:
    # Sanitise session_id to prevent path traversal
    safe_id = "".join(c for c in session_id if c.isalnum() or c == "-")
    return _sessions_dir() / f"{safe_id}.json"


async def load_session(session_id: str) -> dict | None:
    """Load a session from disk. Returns None if not found."""
    path = _session_path(session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load session {session_id}: {e}")
        return None


async def save_session(session_id: str, messages: list[dict]) -> None:
    """Save/update a session file."""
    path = _session_path(session_id)
    now = datetime.now(timezone.utc).isoformat()

    if path.exists():
        try:
            existing = json.loads(path.read_text())
            created = existing.get("created_at", now)
        except (json.JSONDecodeError, OSError):
            created = now
    else:
        created = now

    data = {
        "session_id": session_id,
        "created_at": created,
        "updated_at": now,
        "messages": messages,
    }

    path.write_text(json.dumps(data, indent=2, default=str))
    logger.info(f"Session {session_id}: saved {len(messages)} messages")


async def list_sessions(limit: int = 10) -> list[dict]:
    """List recent sessions by modification time."""
    sessions_dir = _sessions_dir()
    files = sorted(sessions_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

    result = []
    for f in files[:limit]:
        try:
            data = json.loads(f.read_text())
            preview = ""
            for msg in data.get("messages", []):
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    preview = msg["content"][:80]
                    break
            result.append({
                "session_id": data.get("session_id", f.stem),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "message_count": len(data.get("messages", [])),
                "preview": preview,
            })
        except (json.JSONDecodeError, OSError):
            continue

    return result
