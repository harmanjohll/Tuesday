"""Loads Tuesday's knowledge files and assembles the system prompt."""

from __future__ import annotations

from pathlib import Path

from app.config import settings

# Order matters: personality first (defines how Tuesday speaks),
# then user knowledge (defines who Tuesday serves).
KNOWLEDGE_FILES = [
    "tuesday_personality.md",
    "tuesday_instructions.md",
    "identity.md",
    "disposition.md",
    "expertise.md",
    "preferences.md",
    "principles.md",
    "context.md",
    "style.md",
    "session_summaries.md",
]


# Role-specific knowledge subsets for Mind Castle agents
ROLE_KNOWLEDGE = {
    "strategic": [
        "tuesday_personality.md", "identity.md", "context.md",
        "principles.md", "disposition.md", "expertise.md",
    ],
    "advocate": [
        "tuesday_personality.md", "identity.md", "context.md",
        "principles.md",
    ],
    "mentor": [
        "tuesday_personality.md", "identity.md", "disposition.md",
        "principles.md", "context.md",
    ],
    "writer": [
        "tuesday_personality.md", "identity.md", "context.md",
        "style.md", "preferences.md",
    ],
    "builder": [
        "tuesday_personality.md", "identity.md", "context.md",
        "expertise.md",
    ],
    "consolidator": [
        "tuesday_personality.md", "identity.md", "context.md",
        "principles.md",
    ],
}


# Condensed subset for background services (briefing, reflection, session-start).
# Full personality + core identity, but skips session_summaries, expertise, style.
CONDENSED_FILES = [
    "tuesday_personality.md",
    "tuesday_instructions.md",
    "identity.md",
    "disposition.md",
    "principles.md",
]


def load_condensed_knowledge(knowledge_dir: Path | None = None) -> str:
    """Load a condensed knowledge subset for background services.

    Includes personality, instructions, identity, disposition, and principles —
    enough for Tuesday's voice and Harman's priorities, without the full prompt cost.
    """
    knowledge_dir = knowledge_dir or settings.knowledge_dir
    sections: list[str] = []
    for filename in CONDENSED_FILES:
        filepath = knowledge_dir / filename
        if filepath.exists():
            content = filepath.read_text().strip()
            if content:
                sections.append(content)
    return "\n\n---\n\n".join(sections) if sections else ""


def load_knowledge_for_role(role: str, knowledge_dir: Path | None = None) -> str:
    """Load role-specific subset of knowledge files for an agent."""
    knowledge_dir = knowledge_dir or settings.knowledge_dir

    files_to_load = ROLE_KNOWLEDGE.get(role, KNOWLEDGE_FILES)
    sections: list[str] = []
    for filename in files_to_load:
        filepath = knowledge_dir / filename
        if filepath.exists():
            content = filepath.read_text().strip()
            if content:
                sections.append(content)

    # For Gemini-backed agents (advocate role), append abridged reflections
    if role == "advocate":
        try:
            import asyncio
            from app.services.reflection_service import get_abridged_reflections
            # Use sync-safe call since this may be called from sync context
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't await in sync context — skip
                pass
            else:
                abridged = loop.run_until_complete(get_abridged_reflections())
                if abridged:
                    sections.append(abridged)
        except Exception:
            pass  # Reflections not available yet — that's fine

    return "\n\n---\n\n".join(sections) if sections else ""


def load_knowledge(knowledge_dir: Path | None = None) -> str:
    """Read all knowledge files and concatenate into a system prompt."""
    knowledge_dir = knowledge_dir or settings.knowledge_dir
    sections: list[str] = []

    for filename in KNOWLEDGE_FILES:
        filepath = knowledge_dir / filename
        if filepath.exists():
            content = filepath.read_text().strip()
            if content:
                sections.append(content)

    # Also load recent monthly summaries (last 2 months)
    summaries_dir = knowledge_dir / "summaries"
    if summaries_dir.exists():
        summary_files = sorted(summaries_dir.glob("*.md"), reverse=True)[:2]
        for sf in summary_files:
            content = sf.read_text().strip()
            if content:
                sections.append(content)

    if not sections:
        return _fallback_prompt()

    return "\n\n---\n\n".join(sections)


def _fallback_prompt() -> str:
    return (
        "You are Tuesday, a personal AI assistant. "
        "You are competent, direct, and have a dry wit. "
        "Your knowledge files haven't been set up yet, "
        "so introduce yourself and let the user know."
    )
