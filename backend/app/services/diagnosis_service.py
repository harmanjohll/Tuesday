"""Self-diagnosis service — Tuesday's ability to identify and fix his own bugs.

When a tool fails, this service:
1. Captures the error with full context
2. Determines if it's a code bug (vs transient network issue)
3. Reads the relevant source file from GitHub
4. Diagnoses the root cause using Claude
5. Proposes a fix via GitHub PR (never auto-merges)
6. Notifies Harman at next conversation

Safety rails:
- Never auto-deploys — PRs require human approval
- Filters transient errors (timeouts, rate limits, auth)
- Max 3 PRs per day
- All diagnoses logged for review
"""

from __future__ import annotations

import json
import logging
import traceback as tb_module
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger("tuesday.diagnosis")

SGT = timezone(timedelta(hours=8))

# Track daily PR count to avoid flooding
_daily_pr_count = 0
_daily_pr_date: str = ""
MAX_DAILY_PRS = 3

# Pending notifications for Harman
_pending_notifications: list[dict] = []

# Transient errors that should NOT trigger diagnosis
TRANSIENT_PATTERNS = [
    "timeout", "timed out", "rate limit", "429", "503", "502",
    "connection refused", "connection reset", "network",
    "auth expired", "re-login", "No valid token",
    "Google auth expired", "Authentication expired",
]


def should_diagnose(error: Exception, tool_name: str) -> bool:
    """Determine if an error warrants code diagnosis (vs transient)."""
    error_str = str(error).lower()

    # Skip transient errors
    for pattern in TRANSIENT_PATTERNS:
        if pattern.lower() in error_str:
            return False

    # These error types usually indicate code bugs
    diagnosable_types = (
        KeyError, TypeError, ValueError, AttributeError,
        IndexError, ImportError, NameError, FileNotFoundError,
    )
    if isinstance(error, diagnosable_types):
        return True

    # If it's a generic Exception with a non-transient message, diagnose
    if "Error" in str(type(error).__name__):
        return True

    return False


def capture_error(
    tool_name: str,
    tool_input: dict,
    error: Exception,
    messages: list[dict] | None = None,
) -> dict:
    """Capture a tool error with full context. Writes to structured log."""
    now = datetime.now(SGT)
    error_id = f"err_{now.strftime('%Y%m%d_%H%M%S')}_{tool_name}"

    entry = {
        "error_id": error_id,
        "timestamp": now.isoformat(),
        "tool_name": tool_name,
        "tool_input": {k: str(v)[:200] for k, v in tool_input.items()},
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": tb_module.format_exc(),
        "conversation_context": _extract_context(messages) if messages else None,
        "diagnosis": None,
        "proposal": None,
        "notified": False,
    }

    # Write to error log
    errors_dir = settings.logs_dir / "errors"
    errors_dir.mkdir(parents=True, exist_ok=True)
    log_file = errors_dir / f"{now.strftime('%Y-%m-%d')}.jsonl"

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info(f"Captured error {error_id}: {type(error).__name__}: {error}")
    return entry


def _extract_context(messages: list[dict] | None) -> list[str]:
    """Extract last 3 user messages for context."""
    if not messages:
        return []
    user_msgs = [m for m in messages if m.get("role") == "user"]
    return [
        str(m.get("content", ""))[:200]
        for m in user_msgs[-3:]
    ]


async def diagnose(error_entry: dict) -> dict | None:
    """Analyze an error against the codebase to find root cause."""
    global _daily_pr_count, _daily_pr_date

    # Rate limit check
    today = datetime.now(SGT).strftime("%Y-%m-%d")
    if today != _daily_pr_date:
        _daily_pr_count = 0
        _daily_pr_date = today
    if _daily_pr_count >= MAX_DAILY_PRS:
        logger.info("Daily PR limit reached, skipping diagnosis")
        return None

    tool_name = error_entry["tool_name"]
    error_msg = error_entry["error_message"]
    traceback_str = error_entry["traceback"]

    # Map tool names to likely source files
    file_map = {
        "gmail_": "backend/app/services/gmail_service.py",
        "gcal_": "backend/app/services/gcalendar_service.py",
        "gdrive_": "backend/app/services/gdrive_service.py",
        "outlook_": "backend/app/services/outlook_service.py",
        "github_": "backend/app/tools/executor.py",
        "web_search": "backend/app/tools/executor.py",
        "create_presentation": "backend/app/services/document_generator.py",
        "create_document": "backend/app/services/document_generator.py",
        "run_python": "backend/app/services/sandbox_service.py",
        "spawn_agent": "backend/app/services/agent_service.py",
        "assign_agent": "backend/app/services/agent_service.py",
        "analyze_reference": "backend/app/tools/executor.py",
    }

    # Find likely source file
    source_file = "backend/app/tools/executor.py"  # default
    for prefix, path in file_map.items():
        if tool_name.startswith(prefix):
            source_file = path
            break

    # Also check traceback for file paths
    for line in traceback_str.split("\n"):
        if "app/" in line and ".py" in line:
            match = __import__("re").search(r'File ".*?/(app/\S+\.py)"', line)
            if match:
                source_file = f"backend/{match.group(1)}"
                break

    # Read the source file from GitHub
    try:
        from app.tools.executor import execute_tool
        source_content = await execute_tool("github_manage_repo", {
            "owner": "harmanjohll",
            "repo": "Tuesday",
            "action": "get_file",
            "path": source_file,
        })
    except Exception as e:
        logger.error(f"Could not read source file for diagnosis: {e}")
        return None

    # Ask Claude to diagnose
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = f"""You are Tuesday's self-diagnosis system. A tool has failed. Analyze the error and source code to find the root cause.

## Error Details
- Tool: {tool_name}
- Error Type: {error_entry['error_type']}
- Error Message: {error_msg}

## Traceback
```
{traceback_str}
```

## Source File: {source_file}
```python
{source_content[:15000]}
```

## Task
1. Identify the root cause (be specific — line number, variable, logic error)
2. Assess confidence: HIGH (definitely this), MEDIUM (likely this), LOW (uncertain)
3. Assess severity: CRITICAL (system broken), HIGH (feature broken), MEDIUM (degraded), LOW (cosmetic)
4. Suggest a specific fix (exact code change)

Respond in this JSON format:
{{
    "root_cause": "description of the bug",
    "affected_file": "{source_file}",
    "affected_lines": "line numbers",
    "confidence": "high|medium|low",
    "severity": "critical|high|medium|low",
    "explanation": "why this fix works",
    "suggested_fix": "the exact code to change — show old and new"
}}

If this is NOT a code bug (e.g., bad user input, expected API behavior), return:
{{"root_cause": "not_a_bug", "explanation": "why"}}"""

    try:
        response = await client.messages.create(
            model=settings.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        diagnosis_text = response.content[0].text if response.content else None
        if not diagnosis_text:
            return None

        # Parse JSON from response
        json_match = __import__("re").search(r"\{[\s\S]*\}", diagnosis_text)
        if not json_match:
            return None

        diagnosis = json.loads(json_match.group())

        if diagnosis.get("root_cause") == "not_a_bug":
            logger.info(f"Diagnosis: not a code bug — {diagnosis.get('explanation', '')}")
            return None

        # Update the error entry
        error_entry["diagnosis"] = diagnosis
        logger.info(f"Diagnosed {error_entry['error_id']}: {diagnosis.get('root_cause', 'unknown')}")

        return diagnosis

    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        return None


async def propose_fix(diagnosis: dict, error_entry: dict) -> dict | None:
    """Create a GitHub PR with the proposed fix."""
    global _daily_pr_count

    if not diagnosis or diagnosis.get("confidence") == "low":
        return None

    try:
        from app.tools.executor import execute_tool

        error_id = error_entry["error_id"]
        tool_name = error_entry["tool_name"]
        root_cause = diagnosis.get("root_cause", "Unknown")
        affected_file = diagnosis.get("affected_file", "unknown")
        explanation = diagnosis.get("explanation", "")
        suggested_fix = diagnosis.get("suggested_fix", "")
        confidence = diagnosis.get("confidence", "unknown")
        severity = diagnosis.get("severity", "unknown")

        # Create GitHub issue
        issue_body = (
            f"## Self-Diagnosed Error\n\n"
            f"**Tool:** `{tool_name}`\n"
            f"**Error:** `{error_entry['error_type']}: {error_entry['error_message']}`\n"
            f"**Confidence:** {confidence}\n"
            f"**Severity:** {severity}\n\n"
            f"## Root Cause\n{root_cause}\n\n"
            f"## Affected File\n`{affected_file}`\n\n"
            f"## Explanation\n{explanation}\n\n"
            f"## Suggested Fix\n```\n{suggested_fix}\n```\n\n"
            f"---\n*Generated by Tuesday's self-diagnosis system*"
        )

        issue_result = await execute_tool("github_create_issue", {
            "owner": "harmanjohll",
            "repo": "Tuesday",
            "title": f"[Self-Diagnosis] Fix {tool_name}: {root_cause[:60]}",
            "body": issue_body,
        })

        _daily_pr_count += 1

        # Add to pending notifications
        notification = {
            "error_id": error_id,
            "tool_name": tool_name,
            "root_cause": root_cause,
            "confidence": confidence,
            "severity": severity,
            "issue_result": issue_result[:200],
        }
        _pending_notifications.append(notification)

        logger.info(f"Proposed fix for {error_id}: issue created")
        return notification

    except Exception as e:
        logger.error(f"Failed to propose fix: {e}")
        return None


def get_pending_notifications() -> list[dict]:
    """Get unnotified diagnoses. Called at conversation start."""
    return list(_pending_notifications)


def clear_notifications() -> None:
    """Clear pending notifications after surfacing to Harman."""
    _pending_notifications.clear()


async def run_diagnosis_pipeline(
    tool_name: str,
    tool_input: dict,
    error: Exception,
    messages: list[dict] | None = None,
) -> None:
    """Full pipeline: capture → diagnose → propose. Runs as background task."""
    try:
        if not should_diagnose(error, tool_name):
            return

        entry = capture_error(tool_name, tool_input, error, messages)
        diagnosis = await diagnose(entry)

        if diagnosis and diagnosis.get("confidence") in ("high", "medium"):
            await propose_fix(diagnosis, entry)

    except Exception as e:
        # Never let diagnosis crash the server
        logger.error(f"Diagnosis pipeline failed: {e}")
