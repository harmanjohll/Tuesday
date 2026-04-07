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
from app.services.knowledge_loader import load_knowledge, load_knowledge_for_role
from app.tools.definitions import TOOLS
from app.tools.executor import execute_tool

logger = logging.getLogger("tuesday.agents")

SGT = timezone(timedelta(hours=8))

_store = AgentStore(settings.agents_dir)
_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
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
        "github_read_file", "github_create_file", "github_create_branch",
        "github_create_pull_request",
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
                tools=_get_agent_tools(agent),
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
        agent_tools = _get_agent_tools(agent)
        tool_log: list[dict] = []

        for _round in range(MAX_TOOL_ROUNDS):
            response = await _client.messages.create(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=system_prompt,
                messages=working_messages,
                tools=agent_tools,
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

            # Execute tools and log results
            tool_results = []
            for block in assistant_content:
                if block.get("type") == "tool_use":
                    tool_name = block["name"]
                    tool_input = block["input"]
                    logger.info(f"Agent {agent.name} (background) executing tool: {tool_name}")

                    result = await execute_tool(tool_name, tool_input)
                    tool_log.append({"name": tool_name, "input": tool_input, "result": result})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                    })

            working_messages.append({"role": "user", "content": tool_results})

            # Update progress
            agent.progress = min(0.9, 0.1 + (_round + 1) * 0.15)
            _store.save(agent)

        # Extract final text response
        result_text = ""
        for block in assistant_content:
            if block.get("type") == "text":
                result_text += block["text"]

        if not result_text:
            result_text = "Task completed (tools were used but no final summary generated)."

        # Verify task completion
        verification = _verify_task_completion(task, result_text, tool_log)

        agent.messages.append({"role": "assistant", "content": result_text})
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
