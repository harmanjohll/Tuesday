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
_pending_results: list[dict] = []  # Completed results awaiting user's next message

MAX_TOOL_ROUNDS = 10  # Safety limit for tool loops

# Regex patterns for detecting file/template references in task text
import re

_FILE_REF_PATTERNS = [
    re.compile(r"SMC\s*#?\s*(\d+)", re.IGNORECASE),        # SMC#04, SMC 04
    re.compile(r"[Ss]ession\s*(\d+)"),                       # Session 1, session 3
    re.compile(r"[A-Z]{2,}[-_]\d+"),                         # AB-01, SL_2
    re.compile(r"5-to-[Tt]hrive"),                           # 5-to-Thrive
    re.compile(r"SHARP|VOICE|STAR|DREAM", re.IGNORECASE),   # Known framework names
]


def _detect_file_references(task: str) -> list[str]:
    """Extract file references from task text for exemplar fetching."""
    refs = []
    for pattern in _FILE_REF_PATTERNS:
        matches = pattern.findall(task)
        for m in matches:
            ref = m if isinstance(m, str) else pattern.pattern
            if ref and ref not in refs:
                refs.append(ref)
    # Also check for quoted filenames
    quoted = re.findall(r'"([^"]+\.\w{2,4})"', task)
    refs.extend(q for q in quoted if q not in refs)
    return refs[:3]  # Max 3 references


# Keyword → skill auto-injection mapping
SKILL_KEYWORDS: dict[str, list[str]] = {
    "presentation_design.md": ["slides", "deck", "presentation", "pptx", "powerpoint", "slide"],
    "speech_writing.md": ["speech", "address", "keynote", "opening remarks", "closing remarks", "ceremony"],
    "persuasive_frameworks.md": ["persuade", "convince", "proposal", "pitch", "advocacy"],
    "critical_analysis.md": ["critique", "analyze", "evaluate", "review", "assessment"],
    "scenario_planning.md": ["scenario", "strategic", "futures", "contingency", "forecast"],
    "coaching_models.md": ["coach", "mentor", "reflect", "feedback", "development"],
    "decision_matrices.md": ["decision", "options", "trade-off", "matrix", "weigh"],
    "reflective_practice.md": ["reflect", "debrief", "lesson learned", "retrospective"],
    "system_design.md": ["system", "architecture", "workflow", "automate", "infrastructure"],
}


def _detect_skills_for_task(task: str) -> list[str]:
    """Return skill filenames relevant to the task text."""
    task_lower = task.lower()
    matched = []
    for skill_file, keywords in SKILL_KEYWORDS.items():
        if any(kw in task_lower for kw in keywords):
            matched.append(skill_file)
    return matched


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


def get_agent_by_name(name: str) -> Optional[Agent]:
    """Find an agent by name (case-insensitive). Returns first match."""
    for agent in _store.list_all():
        if agent.name.lower() == name.lower():
            return agent
    return None


def create_agent(
    name: str,
    role: str,
    color: str = "",
    system_prompt: str = "",
    specialty: str = "",
    skills: list[str] | None = None,
    engine: str = "claude",
) -> Agent:
    """Create a new agent in the Mind Castle. Returns existing agent if name too similar."""
    # Fuzzy match: "Strange-SMC" blocked when "Strange" exists, and vice versa
    name_lower = name.lower()
    for agent in _store.list_all():
        existing_lower = agent.name.lower()
        if existing_lower in name_lower or name_lower in existing_lower:
            logger.info(f"Agent '{name}' too similar to '{agent.name}' ({agent.id}), returning existing")
            return agent

    agent = Agent(
        name=name,
        role=role,
        color=color or _store.next_color(),
        system_prompt=system_prompt,
        specialty=specialty,
        skills=skills or [],
        engine=engine,
    )
    _store.save(agent)
    logger.info(f"Created agent: {agent.name} ({agent.id})")
    return agent


def deduplicate_agents() -> int:
    """Remove duplicate agents (same name). Keeps the one with most messages."""
    all_agents = _store.list_all()
    by_name: dict[str, list[Agent]] = {}
    for agent in all_agents:
        key = agent.name.lower()
        by_name.setdefault(key, []).append(agent)

    removed = 0
    for name, agents in by_name.items():
        if len(agents) <= 1:
            continue
        # Keep the one with the most messages
        agents.sort(key=lambda a: len(a.messages), reverse=True)
        keeper = agents[0]
        for dup in agents[1:]:
            logger.warning(f"Removing duplicate agent: {dup.name} ({dup.id}), keeping {keeper.id}")
            _store.delete(dup.id)
            removed += 1
    return removed


def reset_orphaned_agents() -> int:
    """Reset agents stuck in 'working' status (orphaned from previous runs)."""
    count = 0
    for agent in _store.list_all():
        if agent.status == "working":
            logger.warning(f"Resetting orphaned agent: {agent.name} (was working on: {agent.current_task})")
            agent.status = "idle"
            agent.current_task = ""
            agent.progress = 0.0
            agent.progress_detail = ""
            _store.save(agent)
            count += 1
    return count


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

    # Route Gemini-engine agents (Cap) through the Gemini service
    if agent.engine == "gemini":
        async for chunk in _chat_with_gemini_agent(agent):
            yield chunk
        return

    # Auto-inject skills relevant to the user's message
    original_skills = list(agent.skills)
    extra_skills = _detect_skills_for_task(user_message)
    for s in extra_skills:
        if s not in agent.skills:
            agent.skills.append(s)
            logger.info(f"Auto-injected skill {s} for agent {agent.name} (chat)")

    system_prompt = _build_agent_system_prompt(agent)
    agent.skills = original_skills  # Restore

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


async def _chat_with_gemini_agent(agent: Agent) -> AsyncGenerator[str, None]:
    """Handle chat for Gemini-engine agents (Cap). No tool use, no streaming."""
    from app.services import gemini_service
    from app.services.knowledge_loader import load_knowledge

    # Build a text system prompt (Gemini doesn't use cache_control blocks)
    system_text = (
        f"You are {agent.name}, an AI agent in Harman's Mind Castle.\n"
        f"Your role: {agent.role}\n\n"
    )
    if agent.system_prompt:
        system_text += f"{agent.system_prompt}\n\n"

    # Add skills
    if agent.skills:
        skills_text = load_agent_skills(agent.skills)
        if skills_text:
            system_text += f"---\nYour specialized skills and methods:\n{skills_text}\n\n"

    # Add knowledge context
    knowledge = load_knowledge()
    if knowledge:
        system_text += f"---\nKnowledge about Harman:\n{knowledge}\n"

    try:
        # Recent conversation history for context
        recent_messages = [
            _normalize_message(m) for m in agent.messages[-20:]
        ]

        response_text = await gemini_service.chat(
            messages=recent_messages,
            system_prompt=system_text,
        )

        # Emit the response as SSE tokens (simulated streaming in chunks)
        chunk_size = 50
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i + chunk_size]
            yield f"event:token\ndata:{chunk}\n\n"

        # Save response
        agent.messages.append({"role": "assistant", "content": response_text})
        agent.status = "idle"
        _store.save(agent)
        yield "event:done\ndata:\n\n"

    except Exception as e:
        logger.error(f"Gemini agent {agent.name} chat failed: {e}")
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

    # Route Gemini-engine agents through the Gemini service
    if agent.engine == "gemini":
        await _execute_gemini_task(agent, task)
        return

    # Auto-inject skills relevant to the task
    original_skills = list(agent.skills)
    extra_skills = _detect_skills_for_task(task)
    for s in extra_skills:
        if s not in agent.skills:
            agent.skills.append(s)
            logger.info(f"Auto-injected skill {s} for agent {agent.name}")

    system_prompt = _build_agent_system_prompt(agent)

    # Restore original skills so we don't permanently mutate the agent definition
    agent.skills = original_skills

    try:
        agent.progress = 0.1
        _store.save(agent)

        working_messages = [
            _normalize_message(m) for m in agent.messages[-20:]
        ]

        # Template enforcement: auto-fetch references mentioned in the task
        file_refs = _detect_file_references(task)
        if file_refs:
            from app.tools.executor import _fetch_reference_exemplar
            for ref in file_refs[:2]:
                try:
                    exemplar_result = await _fetch_reference_exemplar({"query": ref, "max_files": 1})
                    if exemplar_result and "REFERENCE EXEMPLAR" in exemplar_result:
                        # Prepend mandatory reference to the last user message
                        last_msg = working_messages[-1]
                        if last_msg["role"] == "user" and isinstance(last_msg["content"], str):
                            working_messages[-1] = {
                                "role": "user",
                                "content": (
                                    f"MANDATORY REFERENCE — follow this structure exactly:\n\n"
                                    f"{exemplar_result}\n\n---\n\n"
                                    f"TASK: {last_msg['content']}"
                                ),
                            }
                        logger.info(f"Auto-fetched template for reference: {ref}")
                except Exception as e:
                    logger.warning(f"Failed to fetch reference '{ref}': {e}")

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

        # Queue result for proactive status on user's next message
        _pending_results.append({
            "agent_name": agent.name,
            "task": task[:100],
            "result_summary": result_text[:500],
            "timestamp": datetime.now(SGT).isoformat(),
        })

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


async def _execute_gemini_task(agent: Agent, task: str) -> None:
    """Execute a background task using Gemini (for Cap and other Gemini agents)."""
    from app.services import gemini_service
    from app.services.knowledge_loader import load_knowledge

    try:
        agent.progress = 0.1
        agent.progress_detail = "Reviewing..."
        _store.save(agent)

        # Build system prompt as plain text
        system_text = (
            f"You are {agent.name}, an AI agent in Harman's Mind Castle.\n"
            f"Your role: {agent.role}\n\n"
        )
        if agent.system_prompt:
            system_text += f"{agent.system_prompt}\n\n"
        if agent.skills:
            skills_text = load_agent_skills(agent.skills)
            if skills_text:
                system_text += f"---\nYour specialized skills:\n{skills_text}\n\n"
        knowledge = load_knowledge()
        if knowledge:
            system_text += f"---\nKnowledge about Harman:\n{knowledge}\n"

        recent_messages = [_normalize_message(m) for m in agent.messages[-20:]]

        agent.progress = 0.5
        agent.progress_detail = "Generating response..."
        _store.save(agent)

        result_text = await gemini_service.chat(
            messages=recent_messages,
            system_prompt=system_text,
        )

        agent.messages.append({"role": "assistant", "content": result_text})
        agent.status = "done"
        agent.progress = 1.0
        agent.progress_detail = ""
        agent.last_active = datetime.now(SGT).isoformat()
        _store.save(agent)

        logger.info(f"Gemini agent {agent.name} completed task: {task[:60]}")

        from app.services.activity_service import log_event
        log_event("agent_complete", f"{agent.name} completed review", task[:100], agent_name=agent.name)

        _pending_results.append({
            "agent_name": agent.name,
            "task": task[:100],
            "result_summary": result_text[:500],
            "timestamp": datetime.now(SGT).isoformat(),
        })

    except Exception as e:
        logger.error(f"Gemini agent {agent.name} task failed: {e}")
        agent.status = "error"
        agent.messages.append({"role": "assistant", "content": f"Review failed: {e}"})
        _store.save(agent)

        from app.services.activity_service import log_event
        log_event("error", f"{agent.name} task failed", str(e)[:200], agent_name=agent.name)
    finally:
        _running_tasks.pop(agent.id, None)


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


def consume_pending_results() -> list[dict]:
    """Pop and return all pending agent results. Called when user sends a message."""
    global _pending_results
    results = list(_pending_results)
    _pending_results.clear()
    return results


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
