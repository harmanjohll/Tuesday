"""Smart task router — routes complex tasks to specialist agents.

Called via the task_pipeline tool. Detects task type and routes to
the appropriate agent(s):
  - research → Strange
  - analysis → Strange then Loki challenges
  - code → Tony
  - challenge → Loki
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.config import settings

logger = logging.getLogger("tuesday.router")

SGT = timezone(timedelta(hours=8))

# Module-level status for real-time UI updates
_router_status: str = ""


def get_router_status() -> str:
    return _router_status


async def route_task(task: str, task_type: str) -> dict:
    """Route a complex task to the appropriate agent(s).

    Returns dict with: result, agent_used, summary.
    """
    global _router_status
    from app.services import agent_service

    logger.info(f"Task router: type={task_type}, task={task[:80]}")

    try:
        if task_type == "research":
            return await _research_pipeline(task)
        elif task_type == "analysis":
            return await _analysis_pipeline(task)
        elif task_type == "code":
            return await _code_pipeline(task)
        elif task_type == "challenge":
            return await _challenge_pipeline(task)
        else:
            return {"result": "", "agent_used": "", "summary": f"Unknown task type: {task_type}"}
    finally:
        _router_status = ""


async def _research_pipeline(task: str) -> dict:
    """Strange investigates → returns findings."""
    global _router_status
    from app.services import agent_service

    strange_id = _get_agent_id("Strange")
    if not strange_id:
        return _error("Agent 'Strange' not found.")

    _router_status = "Strange is researching..."
    await agent_service.assign_task(strange_id, task)
    result = await _wait_for_agent(strange_id, timeout=120)

    summary = _summarize(result, "Strange's research")
    return {"result": result, "agent_used": "Strange", "summary": summary}


async def _analysis_pipeline(task: str) -> dict:
    """Strange analyzes → Loki challenges the analysis."""
    global _router_status
    from app.services import agent_service

    # Step 1: Strange analyzes
    strange_id = _get_agent_id("Strange")
    if not strange_id:
        return _error("Agent 'Strange' not found.")

    _router_status = "Strange is analyzing..."
    await agent_service.assign_task(strange_id, task)
    analysis = await _wait_for_agent(strange_id, timeout=120)

    # Step 2: Loki challenges
    loki_id = _get_agent_id("Loki")
    if not loki_id:
        summary = _summarize(analysis, "Strange's analysis")
        return {"result": analysis, "agent_used": "Strange", "summary": summary + "\n(Loki unavailable for challenge)"}

    _router_status = "Loki is challenging the analysis..."
    challenge_task = (
        f"Challenge this analysis. Find weaknesses, blind spots, and flawed assumptions. "
        f"Be specific. Max 200 words.\n\nAnalysis:\n{analysis[:3000]}"
    )
    await agent_service.assign_task(loki_id, challenge_task)
    challenge = await _wait_for_agent(loki_id, timeout=90)

    summary = (
        f"**Strange's analysis:** {_first_sentences(analysis, 3)}\n\n"
        f"**Loki's challenge:** {_first_sentences(challenge, 3)}"
    )
    return {"result": f"{analysis}\n\n---\nLoki's challenge:\n{challenge}", "agent_used": "Strange + Loki", "summary": summary}


async def _code_pipeline(task: str) -> dict:
    """Tony builds/prototypes → returns result."""
    global _router_status
    from app.services import agent_service

    tony_id = _get_agent_id("Tony")
    if not tony_id:
        return _error("Agent 'Tony' not found.")

    _router_status = "Tony is building..."
    await agent_service.assign_task(tony_id, task)
    result = await _wait_for_agent(tony_id, timeout=180)

    summary = _summarize(result, "Tony's work")
    return {"result": result, "agent_used": "Tony", "summary": summary}


async def _challenge_pipeline(task: str) -> dict:
    """Loki stress-tests an idea → returns critique."""
    global _router_status
    from app.services import agent_service

    loki_id = _get_agent_id("Loki")
    if not loki_id:
        return _error("Agent 'Loki' not found.")

    _router_status = "Loki is challenging..."
    await agent_service.assign_task(loki_id, task)
    result = await _wait_for_agent(loki_id, timeout=90)

    summary = _summarize(result, "Loki's critique")
    return {"result": result, "agent_used": "Loki", "summary": summary}


# --- Helpers ---

def _get_agent_id(name: str) -> str | None:
    from app.services import agent_service
    for agent in agent_service._store.list_all():
        if agent.name.lower() == name.lower():
            return agent.id
    return None


async def _wait_for_agent(agent_id: str, timeout: int = 120) -> str:
    from app.services import agent_service
    elapsed = 0
    interval = 3
    while elapsed < timeout:
        agent = agent_service._store.load(agent_id)
        if agent and agent.status in ("done", "needs_review", "failed", "idle", "error"):
            output = agent_service.get_agent_output(agent_id)
            if output and "not found" not in output.lower():
                return output
            if agent.status != "working":
                return output or ""
        await asyncio.sleep(interval)
        elapsed += interval
        interval = min(interval * 1.5, 10)
    return agent_service.get_agent_output(agent_id) or ""


def _first_sentences(text: str, n: int = 2) -> str:
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return " ".join(sentences[:n])[:300]


def _summarize(result: str, label: str) -> str:
    preview = _first_sentences(result, 3)
    return f"**{label}:** {preview}"


def _error(msg: str) -> dict:
    return {"result": "", "agent_used": "", "summary": f"Router error: {msg}"}
