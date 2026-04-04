"""Execute tools called by Claude."""

from __future__ import annotations

import asyncio
import logging
import shlex
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger("tuesday.tools")

ALLOWED_KNOWLEDGE_FILES = {
    "identity.md", "disposition.md", "expertise.md",
    "preferences.md", "principles.md", "context.md",
    "session_summaries.md",
}

ALLOWED_COMMAND_PREFIXES = {
    "git", "ls", "cat", "grep", "find", "python3",
    "npm", "node", "date", "whoami", "pwd", "echo",
}

COMMAND_TIMEOUT = 10  # seconds


def _log_tool_use(tool_name: str, tool_input: dict, result: str) -> None:
    """Append tool usage to the change log."""
    log_dir = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tool_changes.log"
    ts = datetime.now(timezone.utc).isoformat()
    entry = f"[{ts}] {tool_name} | input={tool_input} | result={result[:200]}\n"
    with open(log_file, "a") as f:
        f.write(entry)


async def execute_tool(name: str, tool_input: dict) -> str:
    """Dispatch and execute a tool. Returns the result string."""
    try:
        if name == "update_knowledge":
            result = await _update_knowledge(tool_input)
        elif name == "save_session_note":
            result = await _save_session_note(tool_input)
        elif name == "read_file":
            result = await _read_file(tool_input)
        elif name == "write_file":
            result = await _write_file(tool_input)
        elif name == "run_command":
            result = await _run_command(tool_input)
        elif name == "web_search":
            result = await _web_search(tool_input)
        elif name == "log_decision":
            result = await _log_decision(tool_input)
        elif name == "check_followups":
            result = await _check_followups(tool_input)
        elif name.startswith("github_"):
            result = await _github_tool(name, tool_input)
        elif name.startswith("outlook_"):
            result = await _outlook_tool(name, tool_input)
        elif name.startswith("gmail_"):
            result = await _gmail_tool(name, tool_input)
        else:
            result = f"Unknown tool: {name}"
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        result = f"Error executing {name}: {e}"

    _log_tool_use(name, tool_input, result)
    return result


# --- Knowledge tools ---

async def _update_knowledge(inp: dict) -> str:
    filename = inp["filename"]
    content = inp["content"]
    mode = inp.get("mode", "append")

    if filename not in ALLOWED_KNOWLEDGE_FILES:
        return f"Denied: '{filename}' is not an allowed knowledge file. Allowed: {', '.join(sorted(ALLOWED_KNOWLEDGE_FILES))}"

    filepath = settings.knowledge_dir / filename

    if mode == "replace":
        filepath.write_text(content)
    else:
        existing = filepath.read_text() if filepath.exists() else ""
        filepath.write_text(existing.rstrip() + "\n\n" + content + "\n")

    from app.services.claude_service import reload_system_prompt
    reload_system_prompt()

    logger.info(f"Updated knowledge file: {filename} (mode={mode})")
    return f"Successfully updated {filename} ({mode})"


async def _save_session_note(inp: dict) -> str:
    note = inp["note"]
    category = inp.get("category", "other")

    filepath = settings.knowledge_dir / "session_summaries.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"- [{ts}] ({category}) {note}"

    existing = filepath.read_text() if filepath.exists() else "# Session Notes\n"
    filepath.write_text(existing.rstrip() + "\n" + entry + "\n")

    from app.services.claude_service import reload_system_prompt
    reload_system_prompt()

    return f"Saved note: {note}"


# --- File tools ---

async def _read_file(inp: dict) -> str:
    path = Path(inp["path"]).expanduser()
    if not path.exists():
        return f"File not found: {path}"
    try:
        content = path.read_text()
        if len(content) > 10000:
            return content[:10000] + "\n... (truncated)"
        return content
    except Exception as e:
        return f"Error reading {path}: {e}"


async def _write_file(inp: dict) -> str:
    path = Path(inp["path"]).expanduser()
    content = inp["content"]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"


# --- Shell tool ---

async def _run_command(inp: dict) -> str:
    command = inp["command"]

    try:
        parts = shlex.split(command)
    except ValueError:
        return "Invalid command syntax"

    if not parts:
        return "Empty command"

    base_cmd = Path(parts[0]).name
    if base_cmd not in ALLOWED_COMMAND_PREFIXES:
        return f"Command '{base_cmd}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_COMMAND_PREFIXES))}"

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=COMMAND_TIMEOUT)
        output = stdout.decode(errors="replace")
        if stderr:
            output += "\nSTDERR: " + stderr.decode(errors="replace")
        if len(output) > 5000:
            output = output[:5000] + "\n... (truncated)"
        return output or "(no output)"
    except asyncio.TimeoutError:
        return f"Command timed out after {COMMAND_TIMEOUT}s"
    except Exception as e:
        return f"Command failed: {e}"


# --- Web search ---

async def _web_search(inp: dict) -> str:
    query = inp["query"]
    count = min(inp.get("count", 5), 10)

    if not settings.brave_search_api_key:
        return (
            "Web search not configured. Set BRAVE_SEARCH_API_KEY in your .env file. "
            "Get a free key at https://brave.com/search/api/ (2000 queries/month free)."
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "X-Subscription-Token": settings.brave_search_api_key,
                    "Accept": "application/json",
                },
                params={"q": query, "count": count},
            )

        if resp.status_code != 200:
            return f"Search API error {resp.status_code}: {resp.text[:200]}"

        data = resp.json()
        results = data.get("web", {}).get("results", [])

        if not results:
            return f"No results found for: {query}"

        lines = []
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            desc = r.get("description", "")
            lines.append(f"**{title}**\n{url}\n{desc}\n")

        return "\n".join(lines)

    except httpx.TimeoutException:
        return "Search timed out. Try again."
    except Exception as e:
        return f"Search failed: {e}"


# --- GitHub tools ---

async def _github_tool(name: str, inp: dict) -> str:
    from app.tools import github_tools

    dispatch = {
        "github_create_repo": github_tools.create_repo,
        "github_list_repos": github_tools.list_repos,
        "github_analyze_repo": github_tools.analyze_repo,
        "github_search_code": github_tools.search_code,
        "github_create_issue": github_tools.create_issue,
        "github_manage_repo": github_tools.manage_repo,
        "github_update_file": github_tools.update_file,
        "github_create_pull_request": github_tools.create_pull_request,
        "github_list_pull_requests": github_tools.list_pull_requests,
    }

    handler = dispatch.get(name)
    if not handler:
        return f"Unknown GitHub tool: {name}"

    return await handler(inp)


# --- Outlook tools ---

async def _outlook_tool(name: str, inp: dict) -> str:
    from app.services import outlook_service

    dispatch = {
        "outlook_list_events": outlook_service.list_events,
        "outlook_create_event": outlook_service.create_event,
        "outlook_update_event": outlook_service.update_event,
        "outlook_get_messages": outlook_service.get_messages,
        "outlook_send_email": outlook_service.send_email,
    }

    handler = dispatch.get(name)
    if not handler:
        return f"Unknown Outlook tool: {name}"

    return await handler(inp)


# --- Gmail tools ---

async def _gmail_tool(name: str, inp: dict) -> str:
    from app.services import gmail_service

    dispatch = {
        "gmail_get_messages": gmail_service.get_messages,
        "gmail_send_email": gmail_service.send_email,
        "gmail_mark_read": gmail_service.mark_read,
        "gmail_archive": gmail_service.archive,
        "gmail_trash": gmail_service.trash,
    }

    handler = dispatch.get(name)
    if not handler:
        return f"Unknown Gmail tool: {name}"

    return await handler(inp)


# --- Decision journal ---

_DECISIONS_FILE = Path(__file__).resolve().parents[2] / "knowledge" / "decisions.md"


async def _log_decision(inp: dict) -> str:
    from datetime import datetime, timezone, timedelta

    decision = inp["decision"]
    context = inp["context"]
    category = inp.get("category", "general")
    follow_up = inp.get("follow_up_date", "")

    sgt = timezone(timedelta(hours=8))
    now = datetime.now(sgt).strftime("%Y-%m-%d")

    entry = f"\n## {now} — {category}\n"
    entry += f"**Decision:** {decision}\n"
    entry += f"**Context:** {context}\n"
    if follow_up:
        entry += f"**Follow-up:** {follow_up}\n"
    entry += f"**Status:** open\n"

    _DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_DECISIONS_FILE, "a") as f:
        f.write(entry)

    result = f"Logged decision: {decision}"
    if follow_up:
        result += f" (follow-up: {follow_up})"
    return result


async def _check_followups(inp: dict) -> str:
    from datetime import datetime, timezone, timedelta
    import re

    days_ahead = inp.get("days_ahead", 7)

    if not _DECISIONS_FILE.exists():
        return "No decisions logged yet."

    content = _DECISIONS_FILE.read_text()
    if not content.strip():
        return "No decisions logged yet."

    sgt = timezone(timedelta(hours=8))
    today = datetime.now(sgt).date()
    cutoff = today + timedelta(days=days_ahead)

    # Parse follow-up dates
    upcoming = []
    current_decision = ""
    current_date = ""
    current_status = ""

    for line in content.split("\n"):
        if line.startswith("## "):
            current_date = line.split("—")[0].replace("## ", "").strip()
        elif line.startswith("**Decision:**"):
            current_decision = line.replace("**Decision:**", "").strip()
        elif line.startswith("**Status:**"):
            current_status = line.replace("**Status:**", "").strip()
        elif line.startswith("**Follow-up:**"):
            fu_date_str = line.replace("**Follow-up:**", "").strip()
            try:
                fu_date = datetime.strptime(fu_date_str, "%Y-%m-%d").date()
                if fu_date <= cutoff and current_status == "open":
                    days_until = (fu_date - today).days
                    if days_until < 0:
                        timing = f"OVERDUE by {-days_until} days"
                    elif days_until == 0:
                        timing = "TODAY"
                    else:
                        timing = f"in {days_until} days ({fu_date_str})"
                    upcoming.append(f"- {current_decision} — follow-up {timing} (logged {current_date})")
            except ValueError:
                pass

    if not upcoming:
        return f"No follow-ups in the next {days_ahead} days."

    return f"Upcoming follow-ups ({len(upcoming)}):\n" + "\n".join(upcoming)
