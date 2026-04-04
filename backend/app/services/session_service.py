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


async def consolidate_session(session_id: str, messages: list[dict]) -> tuple[list[dict], bool]:
    """If the session is too long, summarize old messages, update knowledge, and trim.

    Returns (possibly_trimmed_messages, was_consolidated).
    """
    threshold = settings.consolidation_message_threshold
    keep_recent = settings.consolidation_keep_recent

    if len(messages) < threshold:
        return messages, False

    logger.info(f"Session {session_id}: {len(messages)} messages — consolidating")

    # Split into old (to summarize) and recent (to keep)
    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    # Summarize old messages via Claude
    summary = await _summarize_messages(old_messages)

    # Save summary to knowledge
    await _save_consolidation_summary(summary)

    # Inject summary as context at the top so Tuesday remembers
    context_msg = {
        "role": "user",
        "content": f"[Previous conversation summary: {summary}]",
    }
    ack_msg = {
        "role": "assistant",
        "content": "Understood — I've absorbed the conversation context.",
    }
    trimmed = [context_msg, ack_msg] + recent_messages

    # Persist the trimmed session
    await save_session(session_id, trimmed)

    logger.info(
        f"Session {session_id}: consolidated {len(old_messages)} old messages "
        f"into summary, kept {len(recent_messages)} recent"
    )
    return trimmed, True


async def _summarize_messages(messages: list[dict]) -> str:
    """Use Claude to produce a concise summary of conversation messages."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Format messages into a readable transcript
    lines = []
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str) and content.strip():
            role = m.get("role", "unknown").upper()
            lines.append(f"{role}: {content}")

    transcript = "\n".join(lines)
    # Cap transcript to avoid huge input costs
    if len(transcript) > 30000:
        transcript = transcript[:30000] + "\n... (truncated)"

    resp = await client.messages.create(
        model=settings.model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize this conversation between Harman and Tuesday. "
                    "Focus on: key decisions made, facts learned about Harman, "
                    "action items, preferences expressed, and important context. "
                    "Be concise — under 400 words.\n\n"
                    f"{transcript}"
                ),
            }
        ],
    )
    return resp.content[0].text


async def _save_consolidation_summary(summary: str) -> None:
    """Append a consolidation summary to session_summaries.md and reload prompt."""
    from app.services.claude_service import reload_system_prompt

    filepath = settings.knowledge_dir / "session_summaries.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = f"\n## Consolidation — {ts}\n{summary}\n"

    existing = filepath.read_text() if filepath.exists() else "# Session Notes\n"
    filepath.write_text(existing.rstrip() + "\n" + entry)
    reload_system_prompt()
    logger.info("Consolidation summary saved to session_summaries.md")


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
