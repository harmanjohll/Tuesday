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
    "session_summaries.md", "patterns.md",
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
        elif name == "sync_brain":
            from app.tools import brain_tools
            result = await brain_tools.sync_brain(tool_input)
        elif name == "create_time_capsule":
            from app.tools import brain_tools
            result = await brain_tools.create_time_capsule(tool_input)
        elif name == "list_templates":
            from app.services import template_service
            import json as _json
            templates = template_service.list_templates(tool_input.get("template_type", ""))
            result = _json.dumps(templates, indent=2) if templates else "No templates uploaded yet."
        elif name == "create_presentation":
            from app.services import document_generator
            result = await document_generator.create_presentation(tool_input)
        elif name == "create_document":
            from app.services import document_generator
            result = await document_generator.create_word_document(tool_input)
        elif name == "create_pdf_report":
            from app.services import document_generator
            result = await document_generator.create_pdf_report(tool_input)
        elif name == "set_reminder":
            result = await _set_reminder(tool_input)
        elif name == "list_reminders":
            result = await _list_reminders(tool_input)
        elif name == "dismiss_reminder":
            result = await _dismiss_reminder(tool_input)
        elif name == "run_python":
            from app.services import sandbox_service
            result = await sandbox_service.run_python(tool_input)
        elif name == "query_statistics":
            from app.services import statistics_service
            result = await statistics_service.query_statistics(tool_input)
        elif name == "read_work_calendar":
            from app.services import ics_calendar_service
            result = await ics_calendar_service.read_work_calendar(tool_input)
        elif name == "gcal_list_events":
            from app.services import gcalendar_service
            result = await gcalendar_service.list_events(tool_input)
        elif name == "gcal_create_event":
            from app.services import gcalendar_service
            result = await gcalendar_service.create_event(tool_input)
        elif name == "gcal_update_event":
            from app.services import gcalendar_service
            result = await gcalendar_service.update_event(tool_input)
        elif name == "gcal_delete_event":
            from app.services import gcalendar_service
            result = await gcalendar_service.delete_event(tool_input)
        elif name == "gdrive_list_files":
            from app.services import gdrive_service
            result = await gdrive_service.list_files(tool_input)
        elif name == "gdrive_read_file":
            from app.services import gdrive_service
            result = await gdrive_service.read_file(tool_input)
        elif name == "review_insight_report":
            result = await _review_insight_report(tool_input)
        elif name == "analyze_reference_materials":
            result = await _analyze_reference_materials(tool_input)
        elif name == "fetch_reference_exemplar":
            result = await _fetch_reference_exemplar(tool_input)
        elif name == "gdrive_search":
            from app.services import gdrive_service
            result = await gdrive_service.search_files(tool_input)
        elif name == "gdrive_upload_file":
            from app.services import gdrive_service
            result = await gdrive_service.upload_file(tool_input)
        elif name == "log_decision":
            result = await _log_decision(tool_input)
        elif name == "check_followups":
            result = await _check_followups(tool_input)
        elif name == "spawn_agent":
            result = await _agent_tool_spawn(tool_input)
        elif name == "assign_agent_task":
            result = await _agent_tool_assign(tool_input)
        elif name == "get_agent_status":
            result = await _agent_tool_status(tool_input)
        elif name == "read_agent_output":
            result = await _agent_tool_read(tool_input)
        elif name == "list_agents":
            result = await _agent_tool_list(tool_input)
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

        # Self-diagnosis: capture and analyze code bugs
        if settings.diagnosis_enabled:
            try:
                from app.services.diagnosis_service import should_diagnose, run_diagnosis_pipeline
                if should_diagnose(e, name):
                    asyncio.create_task(run_diagnosis_pipeline(name, tool_input, e))
            except Exception:
                pass  # Never let diagnosis crash the main flow

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

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    entry = f"- [{ts}] ({category}) {note}"

    # Write to both the main file (for backward compat) and monthly file
    filepath = settings.knowledge_dir / "session_summaries.md"
    existing = filepath.read_text() if filepath.exists() else "# Session Notes\n"
    filepath.write_text(existing.rstrip() + "\n" + entry + "\n")

    # Also write to monthly summary
    summaries_dir = settings.knowledge_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    monthly_file = summaries_dir / f"{month}.md"
    monthly_existing = monthly_file.read_text() if monthly_file.exists() else f"# Session Notes — {month}\n"
    monthly_file.write_text(monthly_existing.rstrip() + "\n" + entry + "\n")

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
        "outlook_delete_event": outlook_service.delete_event,
        "outlook_get_messages": outlook_service.get_messages,
        "outlook_send_email": outlook_service.send_email,
        "outlook_mark_read": outlook_service.mark_read,
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


# --- Reminders ---

_REMINDERS_FILE = Path(__file__).resolve().parents[2] / "knowledge" / "reminders.md"


async def _set_reminder(inp: dict) -> str:
    from datetime import datetime, timezone, timedelta
    import uuid

    text = inp["text"]
    due_date = inp["due_date"]
    repeat = inp.get("repeat", "none")

    sgt = timezone(timedelta(hours=8))

    if due_date.lower() == "today":
        due_date = datetime.now(sgt).strftime("%Y-%m-%d")

    reminder_id = uuid.uuid4().hex[:8]

    entry = f"\n## {reminder_id}\n"
    entry += f"**What:** {text}\n"
    entry += f"**Due:** {due_date}\n"
    entry += f"**Repeat:** {repeat}\n"
    entry += f"**Status:** active\n"
    entry += f"**Created:** {datetime.now(sgt).strftime('%Y-%m-%d')}\n"

    _REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_REMINDERS_FILE, "a") as f:
        f.write(entry)

    return f"Reminder set (ID: {reminder_id}): {text} — due {due_date}"


async def _list_reminders(inp: dict) -> str:
    include_done = inp.get("include_done", False)

    if not _REMINDERS_FILE.exists():
        return "No reminders set."

    content = _REMINDERS_FILE.read_text()
    if not content.strip() or "##" not in content:
        return "No reminders set."

    reminders = []
    current_id = ""
    current_text = ""
    current_due = ""
    current_status = ""
    current_repeat = ""

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_id and (include_done or current_status == "active"):
                reminders.append(f"- [{current_id}] {current_text} (due: {current_due}, {current_status}"
                               + (f", repeats {current_repeat}" if current_repeat != "none" else "") + ")")
            current_id = line.replace("## ", "").strip()
            current_text = current_due = current_status = ""
            current_repeat = "none"
        elif line.startswith("**What:**"):
            current_text = line.replace("**What:**", "").strip()
        elif line.startswith("**Due:**"):
            current_due = line.replace("**Due:**", "").strip()
        elif line.startswith("**Status:**"):
            current_status = line.replace("**Status:**", "").strip()
        elif line.startswith("**Repeat:**"):
            current_repeat = line.replace("**Repeat:**", "").strip()

    # Don't forget the last one
    if current_id and (include_done or current_status == "active"):
        reminders.append(f"- [{current_id}] {current_text} (due: {current_due}, {current_status}"
                       + (f", repeats {current_repeat}" if current_repeat != "none" else "") + ")")

    if not reminders:
        return "No active reminders."

    return f"Reminders ({len(reminders)}):\n" + "\n".join(reminders)


async def _dismiss_reminder(inp: dict) -> str:
    reminder_id = inp["reminder_id"]

    if not _REMINDERS_FILE.exists():
        return "No reminders file found."

    content = _REMINDERS_FILE.read_text()
    if f"## {reminder_id}" not in content:
        return f"Reminder {reminder_id} not found."

    # Replace status
    content = content.replace(
        f"## {reminder_id}\n",
        f"## {reminder_id}\n",  # Keep ID
    )
    # Find and replace status for this specific reminder
    lines = content.split("\n")
    in_reminder = False
    for i, line in enumerate(lines):
        if line.strip() == f"## {reminder_id}":
            in_reminder = True
        elif line.startswith("## ") and in_reminder:
            break
        elif in_reminder and line.startswith("**Status:**"):
            lines[i] = "**Status:** done"
            break

    _REMINDERS_FILE.write_text("\n".join(lines))
    return f"Reminder {reminder_id} marked as done."


# --- Mind Castle agent tools ---

async def _agent_tool_spawn(inp: dict) -> str:
    from app.services import agent_service
    agent = agent_service.create_agent(
        name=inp["name"],
        role=inp["role"],
        color=inp.get("color", ""),
        system_prompt=inp.get("system_prompt", ""),
    )
    return (
        f"Agent created: {agent.name} (ID: {agent.id})\n"
        f"Color: {agent.color}\n"
        f"Role: {agent.role}\n"
        f"Use assign_agent_task with agent_id='{agent.id}' to give it work."
    )


async def _agent_tool_assign(inp: dict) -> str:
    from app.services import agent_service
    return await agent_service.assign_task(inp["agent_id"], inp["task"])


async def _agent_tool_status(inp: dict) -> str:
    import json
    from app.services import agent_service
    status = agent_service.get_agent_status(inp["agent_id"])
    return json.dumps(status, indent=2)


async def _agent_tool_read(inp: dict) -> str:
    from app.services import agent_service
    return agent_service.get_agent_output(inp["agent_id"])


async def _agent_tool_list(inp: dict) -> str:
    import json
    from app.services import agent_service
    agents = agent_service.list_agents()
    if not agents:
        return "No agents in the Mind Castle yet. Use spawn_agent to create one."
    return json.dumps(agents, indent=2)


# --- Insight report review ---

async def _review_insight_report(inp: dict) -> str:
    """Mark an insight report as reviewed by Harman."""
    report_date = inp["report_date"]
    status = inp["status"]
    notes = inp.get("notes", "")

    insights_dir = settings.knowledge_dir / "insights"
    report_path = insights_dir / f"{report_date}-weekly.md"

    if not report_path.exists():
        return f"No insight report found for {report_date}."

    content = report_path.read_text()

    # Update review status at the bottom
    review_line = f"\n*Reviewed: {status.upper()}"
    if notes:
        review_line += f" — {notes}"
    review_line += f" ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})*"

    content = content.replace("*Review status: PENDING*", f"*Review status: {status.upper()}*{review_line}")
    report_path.write_text(content)

    return f"Insight report for {report_date} marked as {status}."


# --- Style analysis ---

STYLE_ANALYSIS_PROMPT = """You are analyzing reference materials written or created by Harman — a school principal, physicist, and educator in Singapore. Your task is to build a detailed style profile from these materials.

Analyze the following documents and extract:

## Writing Voice
- Tone (formal, conversational, authoritative, warm, etc.)
- Sentence structure patterns (short/long, simple/complex, active/passive)
- Vocabulary level and distinctive word choices
- How he opens and closes documents/sections
- Use of rhetorical devices (analogies, metaphors, questions, repetition)

## Argumentation & Structure
- How he builds a case or argument
- How he organizes ideas (chronological, thematic, problem-solution)
- How he uses evidence and examples
- Transition patterns between ideas

## Presentation Style
- How slides are structured (text density, visual preference)
- Key themes and frameworks he returns to
- How he sequences a presentation arc
- Titling and heading conventions

## Teaching Approach
- Pedagogical methods visible in the materials
- How he explains complex concepts
- How he engages an audience
- Use of stories, examples, real-world connections

## Recurring Themes & Values
- Ideas that appear across multiple documents
- Core beliefs expressed in the materials
- Phrases, frameworks, or mantras he uses repeatedly

## Distinctive Patterns
- Anything unique to his communication style
- Habits, quirks, signature moves

Write the analysis as a structured markdown file suitable for use as a knowledge file. Use headers and bullet points. Be specific — quote actual phrases where possible. This will be used to make an AI assistant match his voice.

---

MATERIALS TO ANALYZE:

{materials}"""


async def _fetch_reference_exemplar(inp: dict) -> str:
    """Fetch reference files from Drive to use as style exemplars."""
    from app.services import gdrive_service

    query = inp.get("query", "")
    max_files = min(inp.get("max_files", 1), 3)

    if not query:
        return "Error: query is required."

    # Search in the Tuesday reference folder
    files = await gdrive_service.list_folder_contents("Tuesday")
    if isinstance(files, str):
        return f"Error accessing Drive folder: {files}"
    if not files:
        return "No files found in Tuesday folder."

    # Filter by query keyword match (case-insensitive)
    query_lower = query.lower()
    matched = [f for f in files if query_lower in f.get("name", "").lower()]

    if not matched:
        # Return available file names so the caller can refine
        available = [f.get("name", "?") for f in files[:15]]
        return f"No files matching '{query}'. Available files: {', '.join(available)}"

    results = []
    for f in matched[:max_files]:
        name = f.get("name", "Untitled")
        content = await gdrive_service.read_file_extended(f["id"], max_chars=15000)
        if isinstance(content, str) and not content.startswith("Error"):
            results.append(f"### {name}\n\n{content}")
            logger.info(f"Fetched exemplar: {name} ({len(content)} chars)")

    if not results:
        return "Could not read any matching files."

    header = (
        f"=== REFERENCE EXEMPLAR{'S' if len(results) > 1 else ''} "
        f"(Harman's actual writing -- match this voice) ===\n\n"
    )
    return header + "\n\n---\n\n".join(results)


async def _analyze_reference_materials(inp: dict) -> str:
    """Read files from a Drive folder and build a style profile."""
    from anthropic import AsyncAnthropic
    from app.services import gdrive_service
    from app.services.claude_service import reload_system_prompt

    folder_name = inp.get("folder_name", "Tuesday")

    # 1. List files in the folder
    files = await gdrive_service.list_folder_contents(folder_name)
    if isinstance(files, str):
        return files  # Error message
    if not files:
        return f"No files found in '{folder_name}' folder."

    # 2. Read each file (up to 20 files, 30K chars each)
    materials = []
    skipped = []
    for f in files[:20]:
        file_id = f["id"]
        name = f.get("name", "Untitled")
        mime = f.get("mimeType", "")

        # Skip non-readable types (images, videos, etc.)
        if any(skip in mime for skip in ["image/", "video/", "audio/"]):
            skipped.append(name)
            continue

        content = await gdrive_service.read_file_extended(file_id, max_chars=30000)
        if not isinstance(content, str) or content.startswith("Error") or content.startswith("Skipped"):
            skipped.append(f"{name} ({content[:80]})" if isinstance(content, str) else name)
            continue

        materials.append(content)
        logger.info(f"Style analysis: read {name} ({len(content)} chars)")

    if not materials:
        return f"Could not read any files from '{folder_name}'. Skipped: {', '.join(skipped)}"

    combined = "\n\n---\n\n".join(materials)

    # 3. Send to Claude Opus for deep analysis
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = STYLE_ANALYSIS_PROMPT.format(materials=combined)

    # Truncate if total is too large for context
    if len(prompt) > 180000:
        prompt = prompt[:180000] + "\n... (remaining materials truncated)"

    try:
        response = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        analysis = response.content[0].text if response.content else "Analysis failed."
    except Exception as e:
        logger.error(f"Style analysis failed: {e}")
        return f"Style analysis failed: {e}"

    # 4. Write to knowledge/style.md
    style_file = settings.knowledge_dir / "style.md"
    header = "# Harman's Communication Style\n\n*Auto-generated from reference materials in Google Drive.*\n\n"
    style_file.write_text(header + analysis)

    # 5. Reload system prompt
    reload_system_prompt()

    read_count = len(materials)
    skip_count = len(skipped)
    result = f"Style analysis complete. Read {read_count} files"
    if skip_count:
        result += f" (skipped {skip_count} non-text files)"
    result += f". Profile saved to knowledge/style.md and loaded into Tuesday's system prompt."

    return result
