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
    "session_summaries.md",
]


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
