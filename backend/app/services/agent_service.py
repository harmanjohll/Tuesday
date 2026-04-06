"""Agent service — manages Mind Castle agents.

Each agent is a named, persistent AI entity with its own role,
color identity, conversation history, and ability to work on tasks
in the background. Tuesday (the main assistant) can spawn and
delegate to agents, and Harman can interact with them directly.

Agents have FULL tool access — the same tools Tuesday uses (email,
calendar, Drive, web search, document generation, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator, Optional

from anthropic import AsyncAnthropic

from app.config import settings
from app.models.agent import Agent, AgentStore
from app.services.knowledge_loader import load_knowledge, load_agent_skills
from app.tools.definitions import TOOLS
from app.tools.executor import execute_tool

logger = logging.getLogger("tuesday.agents")

SGT = timezone(timedelta(hours=8))

_store = AgentStore(settings.agents_dir)
_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
_running_tasks: dict[str, asyncio.Task] = {}

MAX_TOOL_ROUNDS = 10  # Safety limit for tool loops


def _build_agent_system_prompt(agent: Agent) -> list[dict]:
    """Build the system prompt for an agent — full knowledge + tools context.

    Returns list[dict] with cache_control blocks for Anthropic prompt caching.
    The shared knowledge block is cached; the agent-specific prefix is not.
    """
    prefix = (
        f"You are {agent.name}, an AI agent in Harman's Mind Castle.\n"
        f"Your role: {agent.role}\n\n"
        f"You are part of a system called Tuesday — Harman's personal AI assistant. "
        f"Tuesday is the main intelligence. You are a specialist agent that Tuesday "
        f"or Harman can delegate tasks to.\n\n"
        f"You have access to the SAME tools as Tuesday — email, calendar, Google Drive, "
        f"web search, document generation, code execution, and more. Use them when needed "
        f"to complete tasks thoroughly.\n\n"
        f"Be focused, efficient, and thorough in your work. When given a task, "
        f"complete it fully and report your findings clearly.\n"
    )
    if agent.system_prompt:
        prefix += f"\n{agent.system_prompt}\n"

    # Load agent-specific skills
    if agent.skills:
        skills_text = load_agent_skills(agent.skills)
        if skills_text:
            prefix += f"\n---\nYour specialized skills and methods:\n{skills_text}\n"

    blocks = [{"type": "text", "text": prefix}]

    # Give agents the FULL knowledge context (not truncated to 3000 chars)
    knowledge = load_knowledge()
    if knowledge:
        blocks.append({
            "type": "text",
            "text": f"\n---\nKnowledge about Harman:\n{knowledge}\n",
            "cache_control": {"type": "ephemeral"},
        })

    return blocks


def create_agent(
    name: str,
    role: str,
    color: str = "",
    system_prompt: str = "",
    specialty: str = "",
    skills: list[str] | None = None,
) -> Agent:
    """Create a new agent in the Mind Castle."""
    agent = Agent(
        name=name,
        role=role,
        color=color or _store.next_color(),
        system_prompt=system_prompt,
        specialty=specialty,
        skills=skills or [],
    )
    _store.save(agent)
    logger.info(f"Created agent: {agent.name} ({agent.id})")
    return agent


def backfill_agent_fields(fields_map: dict[str, dict]) -> None:
    """Backfill specialty/skills for existing agents that lack them."""
    for agent in _store.list_all():
        if agent.name in fields_map:
            updated = False
            for field_name, value in fields_map[agent.name].items():
                if not getattr(agent, field_name, None) and value:
                    setattr(agent, field_name, value)
                    updated = True
            if updated:
                _store.save(agent)


def get_agent(agent_id: str) -> Optional[Agent]:
    return _store.load(agent_id)


def list_agents() -> list[dict]:
    return [a.to_summary() for a in _store.list_all()]


def delete_agent(agent_id: str) -> bool:
    # Cancel any running task
    task = _running_tasks.pop(agent_id, None)
    if task and not task.done():
        task.cancel()
    return _store.delete(agent_id)


async def chat_with_agent(
    agent_id: str,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """Stream a conversation with an agent (SSE-style) with full tool use."""
    agent = _store.load(agent_id)
    if not agent:
        yield f"event:error\ndata:Agent {agent_id} not found\n\n"
        return

    agent.status = "working"
    agent.last_active = datetime.now(SGT).isoformat()
    agent.messages.append({"role": "user", "content": user_message})
    _store.save(agent)

    system_prompt = _build_agent_system_prompt(agent)

    try:
        # Use a working copy of messages for the tool loop
        working_messages = [
            _normalize_message(m) for m in agent.messages[-20:]
        ]

        full_text_response = ""

        for _round in range(MAX_TOOL_ROUNDS):
            response = await _client.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=system_prompt,
                messages=working_messages,
                tools=TOOLS,
                stream=True,
            )

            # Collect the response while streaming text
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
                            full_text_response += current_text
                            yield f"event:token\ndata:{current_text}\n\n"
                    elif block.type == "tool_use":
                        current_tool_use = {"id": block.id, "name": block.name}
                        current_tool_input_json = ""

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        current_text += delta.text
                        full_text_response += delta.text
                        yield f"event:token\ndata:{delta.text}\n\n"
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

            # Append assistant message to working copy
            working_messages.append({"role": "assistant", "content": assistant_content})

            # If no tool use, we're done
            if stop_reason != "tool_use":
                break

            # Execute tools
            tool_results = []
            for block in assistant_content:
                if block.get("type") == "tool_use":
                    tool_name = block["name"]
                    tool_input = block["input"]
                    yield f"event:tool\ndata:{tool_name}\n\n"
                    logger.info(f"Agent {agent.name} executing tool: {tool_name}")

                    result = await execute_tool(tool_name, tool_input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                    })

            # Append tool results and continue loop
            working_messages.append({"role": "user", "content": tool_results})

        # Save the final text response to agent history
        agent.messages.append({"role": "assistant", "content": full_text_response})
        agent.status = "idle"
        _store.save(agent)
        yield "event:done\ndata:\n\n"

    except Exception as e:
        logger.error(f"Agent {agent.name} chat failed: {e}")
        agent.status = "error"
        _store.save(agent)
        yield f"event:error\ndata:{str(e)}\n\n"


async def assign_task(agent_id: str, task: str) -> str:
    """Assign a background task to an agent. Returns immediately."""
    agent = _store.load(agent_id)
    if not agent:
        return f"Agent {agent_id} not found."

    if agent.status == "working":
        return f"{agent.name} is already working on: {agent.current_task}"

    agent.status = "working"
    agent.current_task = task
    agent.progress = 0.0
    agent.last_active = datetime.now(SGT).isoformat()
    agent.messages.append({"role": "user", "content": task})
    _store.save(agent)

    # Run in background
    async_task = asyncio.create_task(_execute_task(agent.id, task))
    _running_tasks[agent.id] = async_task

    logger.info(f"Assigned task to {agent.name}: {task[:80]}")
    return f"Task assigned to {agent.name}. Check status with get_agent_status."


async def _execute_task(agent_id: str, task: str) -> None:
    """Execute a task in the background with full tool use."""
    agent = _store.load(agent_id)
    if not agent:
        return

    system_prompt = _build_agent_system_prompt(agent)

    try:
        agent.progress = 0.1
        _store.save(agent)

        working_messages = [
            _normalize_message(m) for m in agent.messages[-20:]
        ]

        for _round in range(MAX_TOOL_ROUNDS):
            response = await _client.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=system_prompt,
                messages=working_messages,
                tools=TOOLS,
            )

            # Collect content blocks
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            working_messages.append({"role": "assistant", "content": assistant_content})

            # If no tool use, we're done
            if response.stop_reason != "tool_use":
                break

            # Execute tools
            tool_results = []
            for block in assistant_content:
                if block.get("type") == "tool_use":
                    tool_name = block["name"]
                    tool_input = block["input"]
                    logger.info(f"Agent {agent.name} (background) executing tool: {tool_name}")

                    result = await execute_tool(tool_name, tool_input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                    })

            working_messages.append({"role": "user", "content": tool_results})

            # Update progress with structured detail
            agent.progress = min(0.9, 0.1 + (_round + 1) * 0.15)
            tools_used = [b["name"] for b in assistant_content if b.get("type") == "tool_use"]
            if tools_used:
                names = ", ".join(tools_used[:2])
                agent.progress_detail = f"Used {names}" + (f" +{len(tools_used)-2} more" if len(tools_used) > 2 else "")
            else:
                agent.progress_detail = f"Analyzing (step {_round + 1})"
            _store.save(agent)

        # Extract final text response
        result_text = ""
        for block in assistant_content:
            if block.get("type") == "text":
                result_text += block["text"]

        if not result_text:
            result_text = "Task completed (tools were used but no final summary generated)."

        agent.messages.append({"role": "assistant", "content": result_text})
        agent.status = "done"
        agent.progress = 1.0
        agent.progress_detail = ""
        agent.last_active = datetime.now(SGT).isoformat()
        _store.save(agent)

        logger.info(f"Agent {agent.name} completed task: {task[:60]}")

        from app.services.activity_service import log_event
        log_event("agent_complete", f"{agent.name} completed task", task[:100], agent_name=agent.name)

    except asyncio.CancelledError:
        agent.status = "idle"
        agent.current_task = ""
        _store.save(agent)
    except Exception as e:
        logger.error(f"Agent {agent.name} task failed: {e}")
        agent.status = "error"
        agent.messages.append({"role": "assistant", "content": f"Task failed: {e}"})
        _store.save(agent)

        from app.services.activity_service import log_event
        log_event("error", f"{agent.name} task failed", str(e)[:200], agent_name=agent.name)
    finally:
        _running_tasks.pop(agent_id, None)


def _normalize_message(msg: dict) -> dict:
    """Ensure message content is in the correct format for the API.

    Agent history stores assistant messages as plain strings,
    but the API needs structured content blocks for tool use to work.
    """
    content = msg.get("content", "")
    if msg["role"] == "assistant" and isinstance(content, str):
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": content}] if content else [{"type": "text", "text": "..."}],
        }
    return msg


def get_agent_status(agent_id: str) -> dict:
    """Get agent status (used by Tuesday tools)."""
    agent = _store.load(agent_id)
    if not agent:
        return {"error": f"Agent {agent_id} not found"}

    result = agent.to_summary()
    # Include last assistant message if done
    if agent.status == "done" and agent.messages:
        for msg in reversed(agent.messages):
            if msg["role"] == "assistant":
                result["last_output"] = msg["content"][:2000]
                break
    return result


def get_agent_output(agent_id: str) -> str:
    """Get the full last output from an agent."""
    agent = _store.load(agent_id)
    if not agent:
        return f"Agent {agent_id} not found."

    for msg in reversed(agent.messages):
        if msg["role"] == "assistant":
            return msg["content"]

    return "No output yet."
