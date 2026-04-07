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

from app.adapters import get_adapter
from app.adapters.types import (
    CanonicalMessage,
    CanonicalToolCall,
    CanonicalToolDef,
    CanonicalToolResult,
)
from app.config import settings
from app.models.agent import Agent, AgentStore
from app.services.knowledge_loader import load_knowledge, load_knowledge_for_role
from app.tools.definitions import TOOLS
from app.tools.executor import execute_tool

logger = logging.getLogger("tuesday.agents")

SGT = timezone(timedelta(hours=8))

_store = AgentStore(settings.agents_dir)
_running_tasks: dict[str, asyncio.Task] = {}

MAX_TOOL_ROUNDS = 10  # Safety limit for tool loops

# Role-based tool access — each agent role gets a curated tool subset
AGENT_TOOL_SETS = {
    "strategic": [
        "web_search", "query_statistics", "read_work_calendar",
        "gcal_list_events", "outlook_list_events",
        "gdrive_list_files", "gdrive_read_file", "gdrive_search",
        "read_file",
        "get_agent_status", "read_agent_output", "list_agents",
        "log_decision", "check_followups",
    ],
    "advocate": [
        "web_search", "gdrive_list_files", "gdrive_read_file", "gdrive_search",
        "read_file", "query_statistics",
        "get_agent_status", "read_agent_output", "list_agents",
    ],
    "mentor": [
        "read_file", "check_followups",
        "get_agent_status", "read_agent_output",
    ],
    "writer": [
        "create_presentation", "create_and_upload_presentation",
        "create_document", "create_pdf_report",
        "gdrive_list_files", "gdrive_read_file", "gdrive_search",
        "gdrive_upload_file",
        "read_file", "write_file",
        "list_templates",
        "get_agent_status", "read_agent_output",
    ],
    "builder": [
        "run_python", "run_command", "read_file", "write_file",
        "github_create_repo", "github_list_repos", "github_analyze_repo",
        "github_search_code", "github_create_issue",
        "github_manage_repo", "github_update_file",
        "github_create_pull_request", "github_list_pull_requests",
        "web_search",
        "create_presentation", "create_document", "create_pdf_report",
        "gdrive_upload_file",
        "get_agent_status", "read_agent_output", "list_agents",
    ],
}


def _get_agent_tools(agent: Agent) -> list[dict]:
    """Return filtered tool list for this agent's role."""
    if not agent.tool_role or agent.tool_role not in AGENT_TOOL_SETS:
        return TOOLS  # Fallback: full access for custom agents
    allowed = set(AGENT_TOOL_SETS[agent.tool_role])
    return [t for t in TOOLS if t["name"] in allowed]


def _resolve_model(agent: Agent) -> str:
    """Get the model string for this agent, falling back to settings default."""
    return agent.model if agent.model else settings.model


def _get_canonical_tools(agent: Agent) -> list[CanonicalToolDef]:
    """Convert raw tool defs to canonical format for adapters."""
    return [
        CanonicalToolDef(name=t["name"], description=t["description"], parameters=t["input_schema"])
        for t in _get_agent_tools(agent)
    ]


def _to_canonical_messages(raw_messages: list[dict]) -> list[CanonicalMessage]:
    """Convert stored agent messages to canonical format.

    Agent history stores messages as {"role": str, "content": str}.
    The adapters need CanonicalMessage objects.
    """
    result = []
    for msg in raw_messages:
        content = msg.get("content", "")
        role = msg.get("role", "user")
        if isinstance(content, str):
            text = content if content else "..."
            result.append(CanonicalMessage(role=role, text=text))
        # Skip structured content blocks (tool use intermediates) —
        # they only exist in working_messages during execution
    return result


def _build_agent_system_prompt(agent: Agent) -> str:
    """Build the system prompt for an agent — role-specific knowledge + tools context."""
    base = (
        f"You are {agent.name}, an AI agent in Harman's Mind Castle.\n"
        f"Your role: {agent.role}\n\n"
        f"You are part of a system called Tuesday — Harman's personal AI assistant. "
        f"Tuesday is the main intelligence. You are a specialist agent that Tuesday "
        f"or Harman can delegate tasks to.\n\n"
        f"You have access to tools relevant to your specialisation. Use them when needed "
        f"to complete tasks thoroughly.\n\n"
        f"Be focused, efficient, and thorough in your work. When given a task, "
        f"complete it fully and report your findings clearly.\n"
    )
    if agent.system_prompt:
        base += f"\n{agent.system_prompt}\n"

    # Role-specific knowledge instead of full dump
    if agent.tool_role:
        knowledge = load_knowledge_for_role(agent.tool_role)
    else:
        knowledge = load_knowledge()
    if knowledge:
        base += f"\n---\nKnowledge about Harman:\n{knowledge}\n"

    return base


def create_agent(
    name: str,
    role: str,
    color: str = "",
    system_prompt: str = "",
) -> Agent:
    """Create a new agent in the Mind Castle.

    If an agent with the same name already exists, returns the existing one
    instead of creating a duplicate.
    """
    for existing in _store.list_all():
        if existing.name.lower() == name.lower():
            logger.info(f"Agent '{name}' already exists ({existing.id}) — returning existing")
            return existing

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
    """Stream a conversation with an agent (SSE-style) with full tool use.

    Uses the model adapter layer — each agent can run on a different
    LLM provider (Claude, Gemini, etc.) based on agent.model.
    """
    agent = _store.load(agent_id)
    if not agent:
        yield f"event:error\ndata:Agent {agent_id} not found\n\n"
        return

    agent.status = "working"
    agent.last_active = datetime.now(SGT).isoformat()
    agent.messages.append({"role": "user", "content": user_message})
    _store.save(agent)

    system_prompt = _build_agent_system_prompt(agent)
    model = _resolve_model(agent)
    adapter = get_adapter(model)
    canonical_tools = _get_canonical_tools(agent)

    try:
        working_messages = _to_canonical_messages(agent.messages[-20:])
        full_text_response = ""

        for _round in range(MAX_TOOL_ROUNDS):
            tool_calls_this_round: list[CanonicalToolCall] = []
            round_text = ""
            stop_reason = "end_turn"

            async for event in adapter.stream(
                model=model,
                system_prompt=system_prompt,
                messages=working_messages,
                tools=canonical_tools,
                max_tokens=settings.max_tokens,
            ):
                if event.type == "text_delta":
                    round_text += event.text
                    full_text_response += event.text
                    yield {"event": "token", "data": event.text}
                elif event.type == "tool_call_end" and event.tool_call:
                    tool_calls_this_round.append(event.tool_call)
                elif event.type == "done":
                    stop_reason = event.stop_reason or "end_turn"

            # Build canonical assistant message
            working_messages.append(CanonicalMessage(
                role="assistant",
                text=round_text,
                tool_calls=tool_calls_this_round,
            ))

            if stop_reason != "tool_use":
                break

            # Execute tools (model-agnostic — same for all providers)
            tool_results: list[CanonicalToolResult] = []
            for tc in tool_calls_this_round:
                yield {"event": "tool", "data": tc.name}
                logger.info(f"Agent {agent.name} executing tool: {tc.name}")
                result = await execute_tool(tc.name, tc.arguments)
                tool_results.append(CanonicalToolResult(
                    tool_call_id=tc.id,
                    name=tc.name,
                    content=result,
                ))

            working_messages.append(CanonicalMessage(
                role="tool_results",
                tool_results=tool_results,
            ))

        # Save final text response to agent history
        agent.messages.append({"role": "assistant", "content": full_text_response})
        agent.current_task = ""
        agent.status = "idle"
        _store.save(agent)
        yield {"event": "done", "data": ""}

    except Exception as e:
        logger.error(f"Agent {agent.name} chat failed: {e}")
        agent.status = "error"
        _store.save(agent)
        yield {"event": "error", "data": str(e)}


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
    """Execute a task in the background with full tool use.

    Uses the model adapter layer — routes to the correct LLM provider
    based on agent.model.
    """
    agent = _store.load(agent_id)
    if not agent:
        return

    system_prompt = _build_agent_system_prompt(agent)
    model = _resolve_model(agent)
    adapter = get_adapter(model)
    canonical_tools = _get_canonical_tools(agent)

    try:
        agent.progress = 0.1
        _store.save(agent)

        working_messages = _to_canonical_messages(agent.messages[-20:])
        tool_log: list[dict] = []
        result_text = ""

        for _round in range(MAX_TOOL_ROUNDS):
            completion = await adapter.complete(
                model=model,
                system_prompt=system_prompt,
                messages=working_messages,
                tools=canonical_tools,
                max_tokens=settings.max_tokens,
            )

            # Build canonical assistant message
            working_messages.append(CanonicalMessage(
                role="assistant",
                text=completion.text,
                tool_calls=completion.tool_calls,
            ))

            if completion.stop_reason != "tool_use":
                result_text = completion.text
                break

            # Execute tools (model-agnostic)
            tool_results: list[CanonicalToolResult] = []
            for tc in completion.tool_calls:
                logger.info(f"Agent {agent.name} (background) executing tool: {tc.name}")
                result = await execute_tool(tc.name, tc.arguments)
                tool_log.append({"name": tc.name, "input": tc.arguments, "result": result})
                tool_results.append(CanonicalToolResult(
                    tool_call_id=tc.id,
                    name=tc.name,
                    content=result,
                ))

            working_messages.append(CanonicalMessage(
                role="tool_results",
                tool_results=tool_results,
            ))

            # Update progress
            agent.progress = min(0.9, 0.1 + (_round + 1) * 0.15)
            _store.save(agent)

        if not result_text:
            result_text = "Task completed (tools were used but no final summary generated)."

        # Verify task completion
        verification = _verify_task_completion(task, result_text, tool_log)

        agent.messages.append({"role": "assistant", "content": result_text})
        agent.current_task = ""
        agent.status = verification["status"]
        agent.progress = 1.0 if verification["verified"] else 0.9
        agent.verification = verification
        agent.last_active = datetime.now(SGT).isoformat()
        _store.save(agent)

        logger.info(
            f"Agent {agent.name} task {verification['status']}: {task[:60]}"
            f" | evidence: {verification['evidence'][:80]}"
        )

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


def _verify_task_completion(task: str, result_text: str, tool_log: list[dict]) -> dict:
    """Verify that an agent actually completed its assigned task.

    Returns dict with: verified (bool), status, evidence, issues.
    """
    import re
    issues = []
    evidence_items = []

    # Check 1: Did any tools return errors?
    for entry in tool_log:
        r = entry.get("result", "")
        if isinstance(r, str) and r.startswith("Error"):
            issues.append(f"Tool {entry['name']} failed: {r[:100]}")

    # Check 2: Were artifacts created?
    downloads = re.findall(r"DOWNLOAD:/[^\n]+", result_text)
    uploads = re.findall(r"Uploaded .+ to Google Drive", result_text)
    emails_sent = re.findall(r"Email sent", result_text)

    for d in downloads:
        evidence_items.append(f"Created file: {d[:80]}")
    for u in uploads:
        evidence_items.append(f"Drive: {u[:80]}")
    for e in emails_sent:
        evidence_items.append("Email sent")

    # Check 3: Meaningful output?
    if not result_text or len(result_text.strip()) < 20:
        issues.append("Agent produced no meaningful output text")

    # Check 4: Truncation? (response ends abruptly)
    if result_text and not result_text.rstrip()[-1:] in ".!?\"')]":
        issues.append("Response may have been truncated (possible max_tokens hit)")

    # Determine status
    if issues and not evidence_items and not result_text.strip():
        status = "failed"
        verified = False
    elif issues:
        status = "needs_review"
        verified = False
    else:
        status = "done"
        verified = True

    return {
        "verified": verified,
        "status": status,
        "evidence": "; ".join(evidence_items) if evidence_items else "Text response only",
        "issues": issues,
    }




def get_agent_status(agent_id: str) -> dict:
    """Get agent status (used by Tuesday tools)."""
    agent = _store.load(agent_id)
    if not agent:
        return {"error": f"Agent {agent_id} not found"}

    result = agent.to_summary()
    # Include last assistant message if done/needs_review
    if agent.status in ("done", "needs_review", "failed") and agent.messages:
        for msg in reversed(agent.messages):
            if msg["role"] == "assistant":
                result["last_output"] = msg["content"][:2000]
                break
    return result


def get_all_agents_status() -> list[dict]:
    """Return status summary for all agents with recent activity — used by session-start sensing."""
    agents = _store.list_all()
    return [
        {
            "name": a.name,
            "status": a.status,
            "last_active": a.last_active,
            "task_preview": (a.messages[-1]["content"][:100] if a.messages else ""),
        }
        for a in agents
        if a.status in ("done", "needs_review", "failed", "working")
    ]


def get_agent_output(agent_id: str) -> str:
    """Get the full last output from an agent."""
    agent = _store.load(agent_id)
    if not agent:
        return f"Agent {agent_id} not found."

    for msg in reversed(agent.messages):
        if msg["role"] == "assistant":
            return msg["content"]

    return "No output yet."
