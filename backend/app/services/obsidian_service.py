"""Obsidian integration — wikilink generation, daily notes, and backlinks index.

Creates Obsidian-compatible markdown with [[wikilinks]] so knowledge files
form a connected graph when opened in an Obsidian vault. Daily notes capture
knowledge updates and conversation summaries with timestamps.
"""

from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

from app.config import settings

SGT = timezone(timedelta(hours=8))

# Knowledge files that can be wikilinked — topic keyword → filename stem
LINKABLE_TOPICS = {
    "identity": "identity",
    "context": "context",
    "expertise": "expertise",
    "principles": "principles",
    "disposition": "disposition",
    "preferences": "preferences",
    "style": "style",
    "tuesday": "tuesday_personality",
    "personality": "tuesday_personality",
    "instructions": "tuesday_instructions",
    "decision journal": "decision_journal",
    "session summaries": "session_summaries",
}


def add_wikilinks(text: str) -> str:
    """Add [[wikilinks]] to text where knowledge topics are referenced.

    Only links the first occurrence of each topic to avoid clutter.
    Skips text that's already wikilinked.
    """
    for topic, stem in LINKABLE_TOPICS.items():
        # Match topic that isn't already inside [[ ]]
        pattern = rf"(?<!\[\[)\b({re.escape(topic)})\b(?!\]\])"
        text = re.sub(pattern, rf"[[{stem}|\1]]", text, flags=re.IGNORECASE, count=1)
    return text


def create_daily_note(content: str, tags: list[str] | None = None) -> Path:
    """Create or append to today's daily note in knowledge/daily/.

    Each entry gets a timestamp header. Content is auto-wikilinked.
    New files get YAML frontmatter for Obsidian metadata.
    """
    daily_dir = settings.knowledge_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(SGT)
    filename = today.strftime("%Y-%m-%d") + ".md"
    filepath = daily_dir / filename

    if not filepath.exists():
        tag_str = ", ".join(tags or [])
        header = (
            f"---\n"
            f"date: {today.strftime('%Y-%m-%d')}\n"
            f"tags: [{tag_str}]\n"
            f"---\n\n"
            f"# {today.strftime('%A, %B %d, %Y')}\n"
        )
        filepath.write_text(header)

    # Append content with wikilinks
    linked_content = add_wikilinks(content)
    timestamp = today.strftime("%H:%M")

    existing = filepath.read_text()
    filepath.write_text(existing + f"\n## {timestamp}\n{linked_content}\n")

    return filepath


def update_backlinks() -> Path:
    """Scan all knowledge markdown files and rebuild the backlinks index.

    Produces knowledge/backlinks_index.md with reverse-link mapping:
    for each wikilinked target, lists all files that reference it.
    """
    knowledge_dir = settings.knowledge_dir
    backlinks: dict[str, list[str]] = {}

    for md_file in knowledge_dir.rglob("*.md"):
        if md_file.name == "backlinks_index.md":
            continue
        content = md_file.read_text()
        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
        for link in links:
            link_lower = link.lower().strip()
            if link_lower not in backlinks:
                backlinks[link_lower] = []
            backlinks[link_lower].append(md_file.stem)

    # Write backlinks index
    index_path = knowledge_dir / "backlinks_index.md"
    lines = ["# Backlinks Index\n",
             "Auto-generated — maps each linked topic to the files that reference it.\n"]
    for target, sources in sorted(backlinks.items()):
        unique_sources = sorted(set(sources))
        lines.append(f"## [[{target}]]")
        for src in unique_sources:
            lines.append(f"- [[{src}]]")
        lines.append("")

    index_path.write_text("\n".join(lines))
    return index_path
