"""Claude API client for Tuesday — with tool use support."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from app.config import settings
from app.services.knowledge_loader import load_knowledge
from app.tools.definitions import TOOLS
from app.tools.executor import execute_tool

logger = logging.getLogger("tuesday.claude")

# Cache the system prompt so we don't re-read files on every request.
# Stored as list[dict] for Anthropic prompt caching support.
_system_prompt: list[dict] | None = None

# Appended as the LAST block in the system prompt — exploits recency bias
# so Claude reads these rules right before generating.
BREVITY_ENFORCEMENT = (
    "\n\n---\n"
    "CRITICAL REMINDERS (read these last, follow them first):\n"
    "1. MAX 1-3 sentences unless Harman explicitly asks for more.\n"
    "2. NEVER narrate your process. No 'Let me...', no 'I'll check...', no progress updates.\n"
    "3. When uncertain about what Harman wants, ASK. Do not guess. Say: 'Need a steer — [specific question]'.\n"
    "4. Silently use tools. Report only the result.\n"
    "5. If a task is running in background, say 'On it.' and stop.\n"
    "6. Do NOT describe which agents you are using or how you are routing the task.\n"
)


def _build_system_blocks(text: str) -> list[dict]:
    """Wrap system prompt text in cache-control blocks for Anthropic prompt caching.

    Knowledge block is cached (large, stable). Brevity enforcement is uncached
    and placed LAST so Claude reads it right before generating.
    """
    return [
        {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": BREVITY_ENFORCEMENT},
    ]


def get_system_prompt() -> list[dict]:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = _build_system_blocks(load_knowledge())
    return _system_prompt


def reload_system_prompt() -> list[dict]:
    """Force-reload knowledge files. Called after knowledge updates."""
    global _system_prompt
    _system_prompt = _build_system_blocks(load_knowledge())
    return _system_prompt


def get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _select_model(messages: list[dict]) -> str:
    """Route to appropriate model based on task complexity.

    Simple lookups → Haiku (fast, cheap)
    Everything else → Opus (quality first)
    """
    haiku_model = "claude-haiku-4-5-20251001"

    if not messages:
        return settings.model

    last_msg = messages[-1]
    content = last_msg.get("content", "")
    if isinstance(content, list):
        content = " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )

    content_lower = content.lower()

    # Only route DOWN to Haiku for truly trivial lookups
    simple_triggers = [
        "what time", "what day", "what date",
        "remind me", "set a reminder", "check my",
        "mark as read", "archive", "list my",
    ]
    if len(content) < 80 and any(t in content_lower for t in simple_triggers):
        logger.info("Model routing: Haiku (simple lookup)")
        return haiku_model

    # Everything else → Opus (the default)
    return settings.model


async def chat(
    messages: list[dict],
    model: str | None = None,
) -> AsyncIterator[dict]:
    """Stream a response from Claude, yielding event dicts.

    Yields:
        {"type": "text", "data": "chunk"}       — text to display
        {"type": "tool_status", "data": "..."}   — tool execution status
        {"type": "done"}                          — stream complete
    """
    client = get_client()
    max_tool_rounds = 10  # safety limit

    for _round in range(max_tool_rounds):
        # Build the streaming request
        selected_model = model or _select_model(messages)
        response = await client.messages.create(
            model=selected_model,
            max_tokens=settings.max_tokens,
            system=get_system_prompt(),
            messages=messages,
            tools=TOOLS,
            stream=True,
        )

        # Collect the full response while streaming text
        assistant_content: list[dict] = []
        current_text = ""
        current_tool_use: dict | None = None
        current_tool_input_json = ""
        stop_reason = None

        async for event in response:
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "text":
                    current_text = block.text
                    if current_text:
                        yield {"type": "text", "data": current_text}
                elif block.type == "tool_use":
                    current_tool_use = {"id": block.id, "name": block.name}
                    current_tool_input_json = ""

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    current_text += delta.text
                    yield {"type": "text", "data": delta.text}
                elif delta.type == "input_json_delta":
                    current_tool_input_json += delta.partial_json

            elif event.type == "content_block_stop":
                if current_tool_use is not None:
                    try:
                        tool_input = json.loads(current_tool_input_json) if current_tool_input_json else {}
                    except json.JSONDecodeError:
                        tool_input = {}
                    assistant_content.append({
                        "type": "tool_use",
                        "id": current_tool_use["id"],
                        "name": current_tool_use["name"],
                        "input": tool_input,
                    })
                    current_tool_use = None
                    current_tool_input_json = ""
                elif current_text:
                    assistant_content.append({"type": "text", "text": current_text})
                    current_text = ""

            elif event.type == "message_delta":
                stop_reason = event.delta.stop_reason

        # Append the assistant message
        messages.append({"role": "assistant", "content": assistant_content})

        # If no tool use, we're done
        if stop_reason != "tool_use":
            break

        # Execute tools and build tool_result messages
        tool_results = []
        for block in assistant_content:
            if block.get("type") == "tool_use":
                tool_name = block["name"]
                tool_input = block["input"]
                yield {"type": "tool_status", "data": f"Running {tool_name}..."}
                logger.info(f"Executing tool: {tool_name}({tool_input})")

                result = await execute_tool(tool_name, tool_input)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })
                yield {"type": "tool_status", "data": f"{tool_name} complete"}

        # Append tool results and loop
        messages.append({"role": "user", "content": tool_results})

    yield {"type": "done"}
