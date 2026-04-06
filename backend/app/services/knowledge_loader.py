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
    "exemplars.md",
    "patterns.md",
    "session_summaries.md",
]

# Appended at the END of the system prompt for recency bias.
BREVITY_ENFORCEMENT = """

---

# CRITICAL: Response Length Rules (OVERRIDE)

Default: 1-3 sentences. No exceptions unless triggered below.

Terse confirmations: "Done." / "On it." / "Sent." / "Set for [date]."

Only elaborate when: Harman asks why/how/explain, clarification genuinely needed,
complex analysis explicitly requested, "tell me more" / "go deeper".

Never: repeat back what Harman said, narrate tool calls step by step,
add preamble ("Great question!"), summarize what you're about to do,
add sign-offs ("let me know if you need anything").
"""


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

    # Load latest insight report (if any)
    insights_dir = knowledge_dir / "insights"
    if insights_dir.exists():
        insight_files = sorted(insights_dir.glob("*.md"), reverse=True)[:1]
        for inf in insight_files:
            content = inf.read_text().strip()
            if content:
                sections.append(f"# Latest Insight Report ({inf.stem})\n\n{content}")

    if not sections:
        return _fallback_prompt()

    return "\n\n---\n\n".join(sections) + BREVITY_ENFORCEMENT


def load_agent_skills(skill_filenames: list[str], knowledge_dir: Path | None = None) -> str:
    """Load specific skill files for an agent."""
    skills_dir = (knowledge_dir or settings.knowledge_dir) / "skills"
    sections: list[str] = []
    for filename in skill_filenames:
        filepath = skills_dir / filename
        if filepath.exists():
            content = filepath.read_text().strip()
            if content:
                sections.append(content)
    return "\n\n---\n\n".join(sections) if sections else ""


def _fallback_prompt() -> str:
    return (
        "You are Tuesday, a personal AI assistant. "
        "You are competent, direct, and have a dry wit. "
        "Your knowledge files haven't been set up yet, "
        "so introduce yourself and let the user know."
    )
