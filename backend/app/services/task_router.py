"""Deterministic task routing — keyword-based agent classifier.

Moves routing decisions out of Claude's judgment into Python code.
Returns a recommended agent name and confidence score based on
keyword matching against the task description.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("tuesday.task_router")

# Agent name → keywords (lowercased) with weights
ROUTE_TABLE: dict[str, dict] = {
    "Matthew": {
        "keywords": [
            "speech", "write", "draft", "address", "keynote", "letter",
            "email draft", "report", "narrative", "essay", "proposal",
            "presentation", "slides", "deck", "pptx", "powerpoint",
        ],
        "priority": 1,
    },
    "Strange": {
        "keywords": [
            "analyze", "review", "strategic", "scenario", "evaluate",
            "assess", "options", "trade-off", "decision", "examine",
            "compare", "weigh", "implications",
        ],
        "priority": 2,
    },
    "Loki": {
        "keywords": [
            "challenge", "critique", "devil", "stress-test", "weakness",
            "flaw", "counter", "argue", "pushback", "risk",
        ],
        "priority": 3,
    },
    "Obi": {
        "keywords": [
            "reflect", "coach", "mentor", "growth", "leadership", "guide",
            "advise", "develop", "mindset", "feedback",
        ],
        "priority": 4,
    },
    "Tony": {
        "keywords": [
            "build", "system", "automate", "code", "technical",
            "design system", "workflow", "prototype", "fix", "debug",
            "engineer", "architecture",
        ],
        "priority": 5,
    },
}


def classify_task(task_text: str) -> tuple[str | None, float]:
    """Classify a task to the best-fit agent.

    Returns (agent_name, confidence) where confidence is 0.0-1.0.
    Returns (None, 0.0) if no clear match (let Claude decide).
    """
    task_lower = task_text.lower()

    scores: dict[str, int] = {}
    for agent_name, config in ROUTE_TABLE.items():
        count = sum(1 for kw in config["keywords"] if kw in task_lower)
        if count > 0:
            scores[agent_name] = count

    if not scores:
        return None, 0.0

    best_agent = max(scores, key=lambda a: (scores[a], -ROUTE_TABLE[a]["priority"]))
    confidence = min(1.0, scores[best_agent] / 3.0)  # 3+ matches = full confidence

    logger.info(f"Task router: '{task_text[:60]}' → {best_agent} (confidence={confidence:.2f})")
    return best_agent, confidence
