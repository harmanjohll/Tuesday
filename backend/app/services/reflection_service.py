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
        f"You are Tuesday, reflecting on the past week's conversations with Harman.\n\n"
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
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.model,
            max_tokens=2048,
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
    """Check if there are unreviewed reflections."""
    d = _reflections_dir()
    if not d.exists():
        return False
    # Pending = files that don't end with _approved.md
    for f in d.glob("*.md"):
        if not f.stem.endswith("_approved"):
            return True
    return False
