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
_system_prompt: str | None = None


HARD_RULES = (
    "CRITICAL RULES (override everything else):\n"
    "1. For ANY writing task (speeches, reports, presentations, letters, proposals): "
    "Call the writing_pipeline tool. Do NOT write it yourself. EVER.\n"
    "2. NEVER output more than 200 words in a single response unless directly answering a question.\n"
    "3. Be decisive. Act, don't narrate. Don't ask permission to use tools — just use them.\n"
    "4. The 5 agents (Strange, Loki, Obi, Matthew, Tony) already exist. NEVER spawn new ones.\n"
    "5. Don't check agent status in a loop. Assign, wait, check once.\n\n"
)


def get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = HARD_RULES + load_knowledge()
    return _system_prompt


def reload_system_prompt() -> str:
    """Force-reload knowledge files. Called after knowledge updates."""
    global _system_prompt
    _system_prompt = load_knowledge()
    return _system_prompt


def get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _select_model(messages: list[dict]) -> str:
    """Route to appropriate model based on task complexity.

    Simple queries → Haiku (fast, cheap)
    Normal conversation → configured model (Sonnet)
    Complex reasoning → Opus (deep thinking)
    """
    haiku_model = "claude-haiku-4-5-20251001"
    opus_model = "claude-opus-4-6"

    if not messages:
        return settings.model

    last_msg = messages[-1]
    content = last_msg.get("content", "")
    if isinstance(content, list):
        # Multimodal — extract text parts
        content = " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )

    content_lower = content.lower()

    # Short, simple queries → Haiku
    simple_triggers = [
        "what time", "what day", "what date", "what's the weather",
        "remind me", "set a reminder", "check my",
        "mark as read", "archive", "list my",
    ]
    if len(content) < 80 and any(t in content_lower for t in simple_triggers):
        logger.info(f"Model routing: Haiku (simple query)")
        return haiku_model

    # Complex reasoning triggers → Opus
    complex_triggers = [
        "analyse", "analyze", "compare", "evaluate", "design",
        "write a report", "write a proposal", "write a speech",
        "create a presentation", "draft a policy", "draft a plan",
        "simulate", "model", "calculate", "solve",
        "what should i", "help me think", "pros and cons",
        "strategy", "framework",
    ]
    if any(t in content_lower for t in complex_triggers):
        logger.info(f"Model routing: Opus (complex reasoning)")
        return opus_model

    # Default → configured model
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
                if tool_name == "writing_pipeline":
                    yield {"type": "tool_status", "data": "Starting writing pipeline..."}
                else:
                    yield {"type": "tool_status", "data": f"Running {tool_name}..."}
                logger.info(f"Executing tool: {tool_name}({tool_input})")

                # For the writing pipeline, poll status while it runs
                if tool_name == "writing_pipeline":
                    import asyncio
                    exec_task = asyncio.create_task(execute_tool(tool_name, tool_input))
                    last_status = ""
                    while not exec_task.done():
                        await asyncio.sleep(3)
                        from app.services.writing_pipeline import get_pipeline_status
                        status = get_pipeline_status()
                        if status and status != last_status:
                            yield {"type": "tool_status", "data": status}
                            last_status = status
                    result = exec_task.result()
                else:
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
