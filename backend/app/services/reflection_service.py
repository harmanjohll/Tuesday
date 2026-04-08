"""Weekly reflection service — metacognitive synthesis.

Runs weekly via APScheduler (Sunday 9 PM SGT). Reads recent sessions,
synthesizes reflections across four dimensions, and saves as a markdown
file for Harman to review at his leisure. NOT shown in chat.

Dimensions:
1. Knowledge gained — facts, context, information
2. Skills observed — capabilities Harman demonstrates
3. Dispositions & values — beliefs, priorities, patterns
4. Metacognitive patterns — thinking habits, decision tendencies
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

from app.config import settings

logger = logging.getLogger("tuesday.reflections")

SGT = timezone(timedelta(hours=8))


def _reflections_dir() -> Path:
    d = settings.reflections_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


async def generate_weekly_reflection() -> dict:
    """Generate a weekly reflection from recent sessions.

    Returns dict with: filepath, summary, week_label.
    """
    logger.info("Generating weekly reflection...")

    # Gather recent sessions
    transcripts = await _gather_recent_sessions(days=7)
    if not transcripts:
        logger.info("No recent sessions for reflection.")
        return {"filepath": "", "summary": "No conversations this week.", "week_label": ""}

    # Synthesize reflection
    now = datetime.now(SGT)
    week_label = now.strftime("%Y-W%V")
    content = await _synthesize_reflection(transcripts, week_label)

    # Save
    filepath = _save_reflection(content, week_label)

    logger.info(f"Weekly reflection saved: {filepath.name}")
    return {
        "filepath": str(filepath),
        "summary": f"Reflection for {week_label} generated ({len(transcripts)} sessions analyzed).",
        "week_label": week_label,
    }


async def _gather_recent_sessions(days: int = 7) -> list[str]:
    """Load sessions modified in the last N days, return as transcripts."""
    sessions_dir = settings.sessions_dir
    if not sessions_dir.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    transcripts = []

    for f in sorted(sessions_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) < cutoff:
            continue
        try:
            data = json.loads(f.read_text())
            messages = data.get("messages", [])
            lines = []
            for m in messages:
                content = m.get("content", "")
                if isinstance(content, str) and content.strip():
                    role = m.get("role", "unknown").upper()
                    lines.append(f"{role}: {content}")
            if lines:
                transcripts.append("\n".join(lines))
        except (json.JSONDecodeError, OSError):
            continue

    return transcripts


async def _synthesize_reflection(transcripts: list[str], week_label: str) -> str:
    """Use Claude to produce a structured reflection."""
    # Combine and cap transcripts
    combined = "\n\n---\n\n".join(transcripts)
    if len(combined) > 30000:
        combined = combined[:30000] + "\n... (truncated)"

    prompt = (
        f"Reflect on the past week's conversations with Harman.\n\n"
        f"Analyze these conversations and produce a structured weekly reflection.\n\n"
        f"IMPORTANT: Write about Harman in second person ('you'). Be specific — cite actual "
        f"conversations and decisions, not generic observations.\n\n"
        f"Structure your reflection exactly as follows:\n\n"
        f"# Weekly Reflection — {week_label}\n\n"
        f"## Knowledge Gained\n"
        f"New facts, context, or information learned about Harman's world this week.\n\n"
        f"## Skills Observed\n"
        f"Capabilities, competencies, and approaches Harman demonstrated.\n\n"
        f"## Dispositions & Values\n"
        f"Beliefs, priorities, and values expressed or reinforced in conversations.\n\n"
        f"## Metacognitive Patterns\n"
        f"How Harman thinks — recurring questions, decision-making tendencies, "
        f"what he gravitates toward, what he avoids, patterns in his reasoning.\n\n"
        f"## Emerging Themes\n"
        f"Cross-cutting patterns that span multiple conversations this week.\n\n"
        f"Keep each section to 3-5 bullet points. Be insightful, not obvious.\n\n"
        f"Conversations:\n{combined}"
    )

    try:
        from app.services.claude_service import get_condensed_system_prompt
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.model,
            max_tokens=2048,
            system=get_condensed_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Reflection synthesis failed: {e}")
        return f"# Weekly Reflection — {week_label}\n\nReflection generation failed: {e}"


def _save_reflection(content: str, week_label: str) -> Path:
    """Save reflection as markdown."""
    filepath = _reflections_dir() / f"{week_label}.md"
    filepath.write_text(content)
    return filepath


async def list_reflections(limit: int = 10) -> list[dict]:
    """List available reflections."""
    d = _reflections_dir()
    files = sorted(d.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)

    result = []
    for f in files[:limit]:
        content = f.read_text()
        # Extract first non-header line as preview
        lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
        preview = lines[0][:100] if lines else ""
        result.append({
            "id": f.stem,
            "filename": f.name,
            "preview": preview,
            "created": datetime.fromtimestamp(f.stat().st_mtime, tz=SGT).isoformat(),
        })
    return result


async def get_reflection(reflection_id: str) -> dict | None:
    """Read a specific reflection."""
    filepath = _reflections_dir() / f"{reflection_id}.md"
    if not filepath.exists():
        return None
    return {
        "id": reflection_id,
        "content": filepath.read_text(),
        "created": datetime.fromtimestamp(filepath.stat().st_mtime, tz=SGT).isoformat(),
    }


async def approve_reflection(reflection_id: str) -> str:
    """Promote approved reflection insights to knowledge files and Obsidian."""
    filepath = _reflections_dir() / f"{reflection_id}.md"
    if not filepath.exists():
        return f"Reflection '{reflection_id}' not found."

    content = filepath.read_text()

    # Append key insights to disposition.md (dispositions/values section)
    try:
        disposition_path = settings.knowledge_dir / "disposition.md"
        if disposition_path.exists():
            existing = disposition_path.read_text()
            disposition_path.write_text(
                existing.rstrip() + f"\n\n## Reflection — {reflection_id}\n"
                + _extract_section(content, "Dispositions & Values")
                + "\n" + _extract_section(content, "Metacognitive Patterns")
                + "\n"
            )
    except Exception as e:
        logger.warning(f"Failed to update disposition.md: {e}")

    # Create Obsidian daily note
    try:
        from app.services.obsidian_service import create_daily_note
        create_daily_note(
            f"### Approved Reflection — {reflection_id}\n{content[:500]}",
            tags=["reflection", "approved"],
        )
    except Exception as e:
        logger.warning(f"Failed to create Obsidian note: {e}")

    # Reload system prompt to pick up new knowledge
    from app.services.claude_service import reload_system_prompt
    reload_system_prompt()

    # Rename file to mark as approved
    approved_path = _reflections_dir() / f"{reflection_id}_approved.md"
    filepath.rename(approved_path)

    return f"Reflection {reflection_id} approved. Insights promoted to knowledge files."


def _extract_section(content: str, heading: str) -> str:
    """Extract a section from markdown by heading."""
    import re
    pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


async def has_pending_reflections() -> bool:
    """Check if there are unreviewed reflections (weekly or micro)."""
    for d in [_reflections_dir(), _micro_dir()]:
        if not d.exists():
            continue
        for f in d.glob("*.json" if d == _micro_dir() else "*.md"):
            if d == _micro_dir():
                try:
                    data = json.loads(f.read_text())
                    if not data.get("approved") and not data.get("dismissed"):
                        return True
                except (json.JSONDecodeError, OSError):
                    continue
            elif not f.stem.endswith("_approved"):
                return True
    return False


# ======================== Micro-Reflections ========================

def _micro_dir() -> Path:
    d = settings.reflections_dir / "micro"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def generate_micro_reflection(session_messages: list[dict]) -> dict | None:
    """Generate a micro-reflection from a single conversation.

    Called after each chat session. Returns a reflection dict or None
    if nothing notable was observed.
    """
    # Extract text messages only
    lines = []
    for m in session_messages:
        content = m.get("content", "")
        if isinstance(content, str) and content.strip():
            role = m.get("role", "unknown").upper()
            lines.append(f"{role}: {content}")

    if len(lines) < 4:
        return None  # Too short to reflect on

    transcript = "\n".join(lines)
    if len(transcript) > 8000:
        transcript = transcript[:8000] + "\n... (truncated)"

    prompt = (
        "Analyze this conversation for metacognitive insights about Harman.\n\n"
        "Look for:\n"
        "- Decisions made or deferred (and why)\n"
        "- Values or priorities expressed\n"
        "- Thinking patterns (how he approaches problems)\n"
        "- New information about his world\n\n"
        "If you find something genuinely insightful, write a brief observation (2-4 sentences). "
        "Be specific — cite what was said. Write in second person ('you').\n\n"
        "If the conversation is routine with nothing notable, respond with exactly: NOTHING_NOTABLE\n\n"
        f"Conversation:\n{transcript}"
    )

    try:
        from app.services.claude_service import get_condensed_system_prompt
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",  # Use Haiku for cost efficiency
            max_tokens=300,
            system=get_condensed_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Micro-reflection failed: {e}")
        return None

    if "NOTHING_NOTABLE" in result_text:
        return None

    # Save
    now = datetime.now(SGT)
    reflection_id = now.strftime("%Y%m%d_%H%M%S")
    reflection = {
        "id": reflection_id,
        "content": result_text,
        "timestamp": now.isoformat(),
        "approved": False,
        "dismissed": False,
    }

    filepath = _micro_dir() / f"{reflection_id}.json"
    filepath.write_text(json.dumps(reflection, indent=2))

    logger.info(f"Micro-reflection saved: {reflection_id}")
    return reflection


async def list_micro_reflections(limit: int = 20, include_approved: bool = False) -> list[dict]:
    """List micro-reflections."""
    d = _micro_dir()
    if not d.exists():
        return []

    files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files[:limit * 2]:  # Read more in case of filtering
        try:
            data = json.loads(f.read_text())
            if data.get("dismissed"):
                continue
            if not include_approved and data.get("approved"):
                continue
            result.append(data)
            if len(result) >= limit:
                break
        except (json.JSONDecodeError, OSError):
            continue
    return result


async def get_micro_reflection(reflection_id: str) -> dict | None:
    """Read a specific micro-reflection."""
    filepath = _micro_dir() / f"{reflection_id}.json"
    if not filepath.exists():
        return None
    try:
        return json.loads(filepath.read_text())
    except (json.JSONDecodeError, OSError):
        return None


async def approve_micro_reflection(reflection_id: str) -> str:
    """Approve a micro-reflection — promote to knowledge files."""
    filepath = _micro_dir() / f"{reflection_id}.json"
    if not filepath.exists():
        return f"Micro-reflection '{reflection_id}' not found."

    data = json.loads(filepath.read_text())
    content = data.get("content", "")

    # Append to disposition.md
    try:
        disposition_path = settings.knowledge_dir / "disposition.md"
        if disposition_path.exists():
            existing = disposition_path.read_text()
            timestamp = data.get("timestamp", reflection_id)
            disposition_path.write_text(
                existing.rstrip() + f"\n\n### Observed {timestamp[:10]}\n{content}\n"
            )
    except Exception as e:
        logger.warning(f"Failed to update disposition.md: {e}")

    # Create Obsidian daily note
    try:
        from app.services.obsidian_service import create_daily_note
        create_daily_note(
            f"### Micro-reflection\n{content}",
            tags=["reflection", "micro", "approved"],
        )
    except Exception as e:
        logger.warning(f"Failed to create Obsidian note: {e}")

    # Mark as approved
    data["approved"] = True
    filepath.write_text(json.dumps(data, indent=2))

    # Reload system prompt
    from app.services.claude_service import reload_system_prompt
    reload_system_prompt()

    return f"Micro-reflection approved. Insight promoted to knowledge files."


async def dismiss_micro_reflection(reflection_id: str) -> str:
    """Dismiss a micro-reflection — mark as not worth keeping."""
    filepath = _micro_dir() / f"{reflection_id}.json"
    if not filepath.exists():
        return f"Micro-reflection '{reflection_id}' not found."

    data = json.loads(filepath.read_text())
    data["dismissed"] = True
    filepath.write_text(json.dumps(data, indent=2))
    return f"Micro-reflection dismissed."


async def get_abridged_reflections(max_chars: int = 4000) -> str:
    """Return an abridged summary of approved reflections for Gemini.

    Concatenates approved micro-reflection content, capped at max_chars.
    Claude gets full access via knowledge files; this is for Gemini's limited context.
    """
    d = _micro_dir()
    if not d.exists():
        return ""

    approved_content: list[str] = []
    total = 0

    for f in sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text())
            if data.get("approved") and not data.get("dismissed"):
                content = data.get("content", "")
                if total + len(content) > max_chars:
                    break
                approved_content.append(f"- {content}")
                total += len(content)
        except (json.JSONDecodeError, OSError):
            continue

    if not approved_content:
        return ""

    return "## Approved Reflections on Harman\n" + "\n".join(approved_content)
