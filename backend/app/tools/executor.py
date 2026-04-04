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
        elif name.startswith("github_"):
            result = await _github_tool(name, tool_input)
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
    }

    handler = dispatch.get(name)
    if not handler:
        return f"Unknown GitHub tool: {name}"

    return await handler(inp)
