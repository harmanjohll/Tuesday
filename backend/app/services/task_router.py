"""Smart task router — routes complex tasks to specialist agents.

Called via the task_pipeline tool. Detects task type and routes to
the appropriate agent(s):

Sequential:
  - research → Strange
  - analysis → Strange then Loki challenges
  - code → Tony
  - challenge → Loki

Parallel (Cap consolidates):
  - parallel_research → Strange + Loki in parallel → Cap synthesizes
  - parallel_analysis → Strange + Tony in parallel → Loki challenges → Cap synthesizes
  - collaborative → Multiple agents in parallel → Cap synthesizes
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

    logger.info(f"Task router: type={task_type}, task={task[:80]}")

    from app.services.activity_tracker import record_event
    record_event("pipeline_start", message=f"Task pipeline ({task_type}): {task[:60]}")

    try:
        if task_type == "research":
            return await _research_pipeline(task)
        elif task_type == "analysis":
            return await _analysis_pipeline(task)
        elif task_type == "code":
            return await _code_pipeline(task)
        elif task_type == "challenge":
            return await _challenge_pipeline(task)
        elif task_type == "parallel_research":
            return await _parallel_research_pipeline(task)
        elif task_type == "parallel_analysis":
            return await _parallel_analysis_pipeline(task)
        elif task_type == "collaborative":
            return await _collaborative_pipeline(task)
        else:
            return {"result": "", "agent_used": "", "summary": f"Unknown task type: {task_type}"}
    finally:
        _router_status = ""


# ======================== Sequential Pipelines ========================

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

    strange_id = _get_agent_id("Strange")
    if not strange_id:
        return _error("Agent 'Strange' not found.")

    _router_status = "Strange is analyzing..."
    await agent_service.assign_task(strange_id, task)
    analysis = await _wait_for_agent(strange_id, timeout=120)

    loki_id = _get_agent_id("Loki")
    if not loki_id:
        summary = _summarize(analysis, "Strange's analysis")
        return {"result": analysis, "agent_used": "Strange", "summary": summary + "\n(Loki unavailable)"}

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


# ======================== Parallel Pipelines ========================

async def _parallel_research_pipeline(task: str) -> dict:
    """Strange + Loki research in parallel → Cap consolidates."""
    global _router_status
    from app.services import agent_service

    strange_id = _get_agent_id("Strange")
    loki_id = _get_agent_id("Loki")
    if not strange_id or not loki_id:
        return await _research_pipeline(task)  # Fallback to sequential

    _router_status = "Strange + Loki researching in parallel..."

    # Launch both simultaneously
    await agent_service.assign_task(strange_id, f"Research this thoroughly. Find facts, data, evidence.\n\n{task}")
    await agent_service.assign_task(loki_id, f"Research counterarguments, risks, and opposing viewpoints.\n\n{task}")

    # Wait for both in parallel
    strange_result, loki_result = await asyncio.gather(
        _wait_for_agent(strange_id, timeout=120),
        _wait_for_agent(loki_id, timeout=120),
    )

    # Cap consolidates
    consolidated = await _consolidate_with_cap(
        {"Strange (research)": strange_result, "Loki (counterpoints)": loki_result},
        task,
    )

    return {
        "result": consolidated,
        "agent_used": "Strange + Loki + Cap",
        "summary": _summarize(consolidated, "Consolidated research"),
    }


async def _parallel_analysis_pipeline(task: str) -> dict:
    """Strange (strategic) + Tony (technical) in parallel → Loki challenges → Cap synthesizes."""
    global _router_status
    from app.services import agent_service

    strange_id = _get_agent_id("Strange")
    tony_id = _get_agent_id("Tony")
    if not strange_id or not tony_id:
        return await _analysis_pipeline(task)  # Fallback

    _router_status = "Strange + Tony analyzing in parallel..."

    # Phase 1: Strange and Tony work simultaneously
    await agent_service.assign_task(strange_id, f"Analyze strategically — scenarios, trade-offs, stakeholder impact.\n\n{task}")
    await agent_service.assign_task(tony_id, f"Analyze technically — feasibility, systems, implementation.\n\n{task}")

    strange_result, tony_result = await asyncio.gather(
        _wait_for_agent(strange_id, timeout=120),
        _wait_for_agent(tony_id, timeout=120),
    )

    # Phase 2: Loki challenges the combined analysis
    loki_id = _get_agent_id("Loki")
    loki_result = ""
    if loki_id:
        _router_status = "Loki is challenging the analysis..."
        challenge_task = (
            f"Challenge this combined analysis. Find weaknesses and blind spots. Max 200 words.\n\n"
            f"Strategic analysis:\n{strange_result[:2000]}\n\n"
            f"Technical analysis:\n{tony_result[:2000]}"
        )
        await agent_service.assign_task(loki_id, challenge_task)
        loki_result = await _wait_for_agent(loki_id, timeout=90)

    # Phase 3: Cap synthesizes everything
    outputs = {
        "Strange (strategic)": strange_result,
        "Tony (technical)": tony_result,
    }
    if loki_result:
        outputs["Loki (challenges)"] = loki_result

    consolidated = await _consolidate_with_cap(outputs, task)

    agents_used = "Strange + Tony + Loki + Cap" if loki_result else "Strange + Tony + Cap"
    return {
        "result": consolidated,
        "agent_used": agents_used,
        "summary": _summarize(consolidated, "Consolidated analysis"),
    }


async def _collaborative_pipeline(task: str) -> dict:
    """All available specialist agents work in parallel → Cap consolidates."""
    global _router_status
    from app.services import agent_service

    strange_id = _get_agent_id("Strange")
    loki_id = _get_agent_id("Loki")
    tony_id = _get_agent_id("Tony")
    obi_id = _get_agent_id("Obi")

    agents_and_tasks = []
    if strange_id:
        agents_and_tasks.append((strange_id, "Strange", f"Analyze strategically.\n\n{task}"))
    if loki_id:
        agents_and_tasks.append((loki_id, "Loki", f"Challenge and stress-test.\n\n{task}"))
    if tony_id:
        agents_and_tasks.append((tony_id, "Tony", f"Assess technical feasibility.\n\n{task}"))
    if obi_id:
        agents_and_tasks.append((obi_id, "Obi", f"Consider the human and leadership angle.\n\n{task}"))

    if not agents_and_tasks:
        return _error("No agents available.")

    names = " + ".join(name for _, name, _ in agents_and_tasks)
    _router_status = f"{names} working in parallel..."

    # Launch all
    for agent_id, _, agent_task in agents_and_tasks:
        await agent_service.assign_task(agent_id, agent_task)

    # Wait for all in parallel
    results = await asyncio.gather(
        *[_wait_for_agent(agent_id, timeout=120) for agent_id, _, _ in agents_and_tasks]
    )

    # Cap consolidates
    outputs = {name: result for (_, name, _), result in zip(agents_and_tasks, results)}
    consolidated = await _consolidate_with_cap(outputs, task)

    return {
        "result": consolidated,
        "agent_used": f"{names} + Cap",
        "summary": _summarize(consolidated, "Collaborative synthesis"),
    }


# ======================== Cap Consolidation ========================

async def _consolidate_with_cap(agent_outputs: dict[str, str], task: str) -> str:
    """Have Cap synthesize outputs from multiple agents."""
    global _router_status
    from app.services import agent_service

    cap_id = _get_agent_id("Cap")
    if not cap_id:
        # Fallback: simple concatenation
        parts = [f"## {name}\n{output}" for name, output in agent_outputs.items()]
        return "\n\n---\n\n".join(parts)

    _router_status = "Cap is synthesizing..."

    # Build consolidation brief
    sections = []
    for name, output in agent_outputs.items():
        sections.append(f"### {name}\n{output[:3000]}")
    agent_block = "\n\n".join(sections)

    consolidation_task = (
        f"Synthesize these agent findings into a coherent, unified response.\n\n"
        f"Original task: {task}\n\n"
        f"Agent outputs:\n{agent_block}\n\n"
        f"Identify agreements, contradictions, and gaps. "
        f"End with a clear recommendation or next step."
    )

    await agent_service.assign_task(cap_id, consolidation_task)
    result = await _wait_for_agent(cap_id, timeout=90)
    return result


# ======================== Helpers ========================

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
