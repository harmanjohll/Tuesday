"""Gemini API wrapper for cross-model QA via Cap agent.

Cap is an independent quality reviewer that runs on Google Gemini 2.5 Pro,
providing genuinely different perspective from Claude-based agents.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger("tuesday.gemini")

_client = None


def _get_model():
    """Lazy-init the Gemini model."""
    global _client
    if _client is None:
        try:
            from google import genai

            _client = genai.Client(api_key=settings.gemini_api_key)
        except ImportError:
            raise RuntimeError(
                "google-genai package not installed. Run: pip install google-genai"
            )
    return _client


async def review(
    content: str,
    criteria: str = "",
    context: str = "",
    system_prompt: str = "",
) -> str:
    """Send content to Gemini for independent review.

    Args:
        content: The text to review (speech draft, proposal, etc.)
        criteria: What to check for (style fidelity, logic, completeness)
        context: Background about the author/audience
        system_prompt: Cap's full personality + knowledge prompt
    """
    if not settings.gemini_api_key:
        return "Gemini API key not configured. Set GEMINI_API_KEY in .env to enable Cap."

    client = _get_model()

    prompt_parts = []
    if system_prompt:
        prompt_parts.append(system_prompt)

    prompt_parts.append(
        "Review the following content. Be specific, direct, and constructive. "
        "Flag anything that doesn't match the criteria or the author's known style."
    )

    if context:
        prompt_parts.append(f"## Context\n{context}")

    if criteria:
        prompt_parts.append(f"## Review Criteria\n{criteria}")

    prompt_parts.append(f"## Content to Review\n{content}")

    full_prompt = "\n\n".join(prompt_parts)

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=full_prompt,
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini review failed: {e}")
        return f"Cap review failed: {str(e)}"


async def chat(
    messages: list[dict],
    system_prompt: str = "",
) -> str:
    """Simple chat with Gemini — used for Cap's conversational mode.

    Args:
        messages: List of {"role": "user"|"assistant", "content": "..."} dicts
        system_prompt: Cap's personality + knowledge context
    """
    if not settings.gemini_api_key:
        return "Gemini API key not configured. Set GEMINI_API_KEY in .env to enable Cap."

    client = _get_model()

    # Build a single prompt from conversation history
    parts = []
    if system_prompt:
        parts.append(f"System instructions:\n{system_prompt}\n")

    for msg in messages:
        role = "User" if msg.get("role") == "user" else "Cap"
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            parts.append(f"{role}: {content}")

    full_prompt = "\n\n".join(parts)

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=full_prompt,
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini chat failed: {e}")
        return f"Cap encountered an error: {str(e)}"
