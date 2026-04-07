"""Agent data model for the Mind Castle system."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

SGT = timezone(timedelta(hours=8))

# Curated color palette for agent orbs
AGENT_COLORS = [
    "#FF6B6B",  # Crimson
    "#4ECDC4",  # Sapphire
    "#FFE66D",  # Amber
    "#A855F7",  # Violet
    "#10B981",  # Emerald
    "#3B82F6",  # Azure
    "#F43F5E",  # Rose
    "#64748B",  # Slate
]


@dataclass
class Agent:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    role: str = ""
    color: str = ""
    system_prompt: str = ""
    tool_role: str = ""  # Maps to AGENT_TOOL_SETS: strategic|advocate|mentor|writer|builder
    model: str = ""  # e.g. "gemini-2.5-flash". Empty = use settings.model default.
    status: str = "idle"  # idle | working | done | needs_review | error | failed
    current_task: str = ""
    progress: float = 0.0
    verification: dict = field(default_factory=dict)  # {verified, evidence, issues}
    messages: list = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(SGT).isoformat()
    )
    last_active: str = field(
        default_factory=lambda: datetime.now(SGT).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_summary(self) -> dict:
        """Lightweight summary for list views (no messages)."""
        result = {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "color": self.color,
            "model": self.model,
            "status": self.status,
            "current_task": self.current_task,
            "progress": self.progress,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "message_count": len(self.messages),
        }
        if self.verification:
            result["verification"] = self.verification
        return result

    @classmethod
    def from_dict(cls, data: dict) -> Agent:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AgentStore:
    """File-based persistence for agents."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._color_index = 0

    def _agent_file(self, agent_id: str) -> Path:
        return self.base_dir / f"{agent_id}.json"

    def next_color(self) -> str:
        color = AGENT_COLORS[self._color_index % len(AGENT_COLORS)]
        self._color_index += 1
        return color

    def save(self, agent: Agent) -> None:
        self._agent_file(agent.id).write_text(
            json.dumps(agent.to_dict(), indent=2)
        )

    def load(self, agent_id: str) -> Optional[Agent]:
        path = self._agent_file(agent_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Agent.from_dict(data)

    def list_all(self) -> list[Agent]:
        agents = []
        for f in sorted(self.base_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                agents.append(Agent.from_dict(data))
            except (json.JSONDecodeError, TypeError):
                continue
        return agents

    def delete(self, agent_id: str) -> bool:
        path = self._agent_file(agent_id)
        if path.exists():
            path.unlink()
            return True
        return False
