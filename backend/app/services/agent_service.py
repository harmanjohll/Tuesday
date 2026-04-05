"""Agent service — manages Mind Castle agents.

Each agent is a named, persistent AI entity with its own role,
color identity, conversation history, and ability to work on tasks
in the background. Tuesday (the main assistant) can spawn and
delegate to agents, and Harman can interact with them directly.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator, Optional

from anthropic import AsyncAnthropic

from app.config import settings
from app.models.agent import Agent, AgentStore
from app.services.knowledge_loader import load_knowledge

logger = logging.getLogger("tuesday.agents")

SGT = timezone(timedelta(hours=8))

_store = AgentStore(settings.agents_dir)
_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
_running_tasks: dict[str, asyncio.Task] = {}


def _build_agent_system_prompt(agent: Agent) -> str:
    """Build the system prompt for an agent."""
    base = (
        f"You are {agent.name}, an AI agent in Harman's Mind Castle.\n"
        f"Your role: {agent.role}\n\n"
        f"You are part of a system called Tuesday — Harman's personal AI assistant. "
        f"Tuesday is the main intelligence. You are a specialist agent that Tuesday "
        f"or Harman can delegate tasks to.\n\n"
        f"Be focused, efficient, and thorough in your work. When given a task, "
        f"complete it fully and report your findings clearly.\n"
    )
    if agent.system_prompt:
        base += f"\nAdditional instructions:\n{agent.system_prompt}\n"

    # Give agents access to Harman's knowledge
    knowledge = load_knowledge()
    if knowledge:
        base += f"\n---\nContext about Harman:\n{knowledge[:3000]}\n"

    return base


def create_agent(
    name: str,
    role: str,
    color: str = "",
    system_prompt: str = "",
) -> Agent:
    """Create a new agent in the Mind Castle."""
    agent = Agent(
        name=name,
        role=role,
        color=color or _store.next_color(),
        system_prompt=system_prompt,
    )
    _store.save(agent)
    logger.info(f"Created agent: {agent.name} ({agent.id})")
    return agent


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
    """Stream a conversation with an agent (SSE-style)."""
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
        async with _client.messages.stream(
            model=settings.model,
            max_tokens=settings.max_tokens,
            system=system_prompt,
            messages=agent.messages[-20:],  # Keep context manageable
        ) as stream:
            full_response = ""
            async for text in stream.text_stream:
                full_response += text
                yield f"event:token\ndata:{text}\n\n"

        agent.messages.append({"role": "assistant", "content": full_response})
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
    """Execute a task in the background."""
    agent = _store.load(agent_id)
    if not agent:
        return

    system_prompt = _build_agent_system_prompt(agent)

    try:
        agent.progress = 0.1
        _store.save(agent)

        response = await _client.messages.create(
            model=settings.model,
            max_tokens=settings.max_tokens,
            system=system_prompt,
            messages=agent.messages[-20:],
        )

        result = response.content[0].text if response.content else "No response generated."
        agent.messages.append({"role": "assistant", "content": result})
        agent.status = "done"
        agent.progress = 1.0
        agent.last_active = datetime.now(SGT).isoformat()
        _store.save(agent)

        logger.info(f"Agent {agent.name} completed task: {task[:60]}")

    except asyncio.CancelledError:
        agent.status = "idle"
        agent.current_task = ""
        _store.save(agent)
    except Exception as e:
        logger.error(f"Agent {agent.name} task failed: {e}")
        agent.status = "error"
        agent.messages.append({"role": "assistant", "content": f"Task failed: {e}"})
        _store.save(agent)
    finally:
        _running_tasks.pop(agent_id, None)


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
