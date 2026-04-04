"""Brain repo sync — pushes knowledge files to harmanjohll/brain on GitHub.

Keeps a portable copy of Harman's identity, preferences, and knowledge
that can be referenced from any Claude Code project or Claude.ai session.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger("tuesday.brain")

API_BASE = "https://api.github.com"
TIMEOUT = 15.0
BRAIN_OWNER = "harmanjohll"
BRAIN_REPO = "brain"

# Knowledge files to sync
SYNC_FILES = [
    "identity.md", "disposition.md", "expertise.md",
    "preferences.md", "principles.md", "context.md",
    "decisions.md",
]

SGT = timezone(timedelta(hours=8))


def _headers() -> dict:
    return {
        "Authorization": f"token {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def sync_brain(inp: dict) -> str:
    """Sync knowledge files to the brain repo."""
    if not settings.github_token:
        return "GitHub token not configured."

    headers = _headers()
    knowledge_dir = settings.knowledge_dir
    synced = []
    errors = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Check if repo exists
        resp = await client.get(
            f"{API_BASE}/repos/{BRAIN_OWNER}/{BRAIN_REPO}",
            headers=headers,
        )
        if resp.status_code == 404:
            return (
                f"Brain repo {BRAIN_OWNER}/{BRAIN_REPO} doesn't exist yet. "
                f"Harman needs to create it on GitHub first (private repo, with a README)."
            )

        for filename in SYNC_FILES:
            filepath = knowledge_dir / filename
            if not filepath.exists():
                continue

            content = filepath.read_text()
            b64_content = base64.b64encode(content.encode()).decode()

            # Check if file exists in repo (need SHA for updates)
            resp = await client.get(
                f"{API_BASE}/repos/{BRAIN_OWNER}/{BRAIN_REPO}/contents/{filename}",
                headers=headers,
            )

            payload = {
                "message": f"Sync {filename} from Tuesday",
                "content": b64_content,
            }

            if resp.status_code == 200:
                existing_sha = resp.json()["sha"]
                # Check if content changed
                existing_content = base64.b64decode(resp.json()["content"]).decode()
                if existing_content.strip() == content.strip():
                    continue  # No change, skip
                payload["sha"] = existing_sha

            resp = await client.put(
                f"{API_BASE}/repos/{BRAIN_OWNER}/{BRAIN_REPO}/contents/{filename}",
                headers=headers,
                json=payload,
            )

            if resp.status_code in (200, 201):
                synced.append(filename)
            else:
                errors.append(f"{filename}: {resp.status_code}")

    if errors:
        return f"Synced {len(synced)} files, but {len(errors)} failed: {', '.join(errors)}"
    if not synced:
        return "Brain repo is already up to date — no changes to sync."
    return f"Synced {len(synced)} files to brain repo: {', '.join(synced)}"


async def create_time_capsule(inp: dict) -> str:
    """Create a dated snapshot tag in the brain repo."""
    if not settings.github_token:
        return "GitHub token not configured."

    # First sync everything
    sync_result = await sync_brain({})

    label = inp.get("label", "")
    now = datetime.now(SGT)
    tag_name = f"capsule-{now.strftime('%Y-%m-%d')}"
    if label:
        tag_name += f"-{label.lower().replace(' ', '-')[:30]}"

    message = inp.get("message", f"Time capsule: {now.strftime('%B %d, %Y')}")
    if label:
        message += f" — {label}"

    headers = _headers()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Get the latest commit SHA on main
        resp = await client.get(
            f"{API_BASE}/repos/{BRAIN_OWNER}/{BRAIN_REPO}/git/ref/heads/main",
            headers=headers,
        )
        if resp.status_code != 200:
            return f"Could not get main branch: {resp.status_code}"

        commit_sha = resp.json()["object"]["sha"]

        # Create annotated tag
        resp = await client.post(
            f"{API_BASE}/repos/{BRAIN_OWNER}/{BRAIN_REPO}/git/tags",
            headers=headers,
            json={
                "tag": tag_name,
                "message": message,
                "object": commit_sha,
                "type": "commit",
            },
        )
        if resp.status_code != 201:
            return f"Could not create tag: {resp.status_code}"

        tag_sha = resp.json()["sha"]

        # Create the reference
        resp = await client.post(
            f"{API_BASE}/repos/{BRAIN_OWNER}/{BRAIN_REPO}/git/refs",
            headers=headers,
            json={
                "ref": f"refs/tags/{tag_name}",
                "sha": tag_sha,
            },
        )

    if resp.status_code == 201:
        return f"Time capsule created: {tag_name}. {sync_result}"
    return f"Tag creation failed: {resp.status_code}. {sync_result}"
