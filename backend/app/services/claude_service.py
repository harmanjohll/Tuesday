"""Claude API client for Tuesday."""

from __future__ import annotations

from collections.abc import AsyncIterator

import anthropic

from app.config import settings
from app.services.knowledge_loader import load_knowledge

# Cache the system prompt so we don't re-read files on every request.
# Restart the server to pick up knowledge file changes.
_system_prompt: str | None = None


def get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = load_knowledge()
    return _system_prompt


def reload_system_prompt() -> str:
    """Force-reload knowledge files. Called after knowledge updates."""
    global _system_prompt
    _system_prompt = load_knowledge()
    return _system_prompt


def get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def chat(
    messages: list[dict],
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream a response from Claude, yielding text chunks."""
    client = get_client()
    async with client.messages.stream(
        model=model or settings.model,
        max_tokens=settings.max_tokens,
        system=get_system_prompt(),
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text
