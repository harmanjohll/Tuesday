"""Execute tools called by Claude."""

from __future__ import annotations

import asyncio
import logging
import shlex
from datetime import datetime, timezone
from pathlib import Path

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
            result = "Web search is not yet implemented. Try answering from your knowledge instead."
        else:
            result = f"Unknown tool: {name}"
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        result = f"Error executing {name}: {e}"

    _log_tool_use(name, tool_input, result)
    return result


async def _update_knowledge(inp: dict) -> str:
    filename = inp["filename"]
    content = inp["content"]
    mode = inp.get("mode", "append")

    if filename not in ALLOWED_KNOWLEDGE_FILES:
        return f"Denied: '{filename}' is not an allowed knowledge file. Allowed: {', '.join(sorted(ALLOWED_KNOWLEDGE_FILES))}"

    filepath = settings.knowledge_dir / filename

    if mode == "replace":
        filepath.write_text(content)
    else:  # append
        existing = filepath.read_text() if filepath.exists() else ""
        filepath.write_text(existing.rstrip() + "\n\n" + content + "\n")

    # Reload the system prompt so future messages use updated knowledge
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


async def _run_command(inp: dict) -> str:
    command = inp["command"]

    # Validate against allowlist
    try:
        parts = shlex.split(command)
    except ValueError:
        return "Invalid command syntax"

    if not parts:
        return "Empty command"

    base_cmd = Path(parts[0]).name  # handles /usr/bin/git -> git
    if base_cmd not in ALLOWED_COMMAND_PREFIXES:
        return f"Command '{base_cmd}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_COMMAND_PREFIXES))}"

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=None,  # inherit env but don't pass secrets
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
