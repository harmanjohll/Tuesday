"""Canonical types for the model adapter layer.

These provider-agnostic dataclasses are the lingua franca between
agent_service and all model adapters. Adapters translate to/from
their native SDK formats; agent_service only sees these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CanonicalToolDef:
    """Provider-agnostic tool definition."""
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass
class CanonicalToolCall:
    """A tool call requested by the model."""
    id: str
    name: str
    arguments: dict


@dataclass
class CanonicalToolResult:
    """Result of executing a tool, fed back to the model."""
    tool_call_id: str
    name: str
    content: str


@dataclass
class CanonicalMessage:
    """Provider-agnostic conversation message."""
    role: str  # "user" | "assistant" | "tool_results"
    text: str = ""
    tool_calls: list[CanonicalToolCall] = field(default_factory=list)
    tool_results: list[CanonicalToolResult] = field(default_factory=list)


@dataclass
class StreamEvent:
    """Normalized streaming event from any provider."""
    type: str  # "text_delta" | "tool_call_end" | "done"
    text: str = ""
    tool_call: CanonicalToolCall | None = None
    stop_reason: str = ""  # "end_turn" | "tool_use" | "max_tokens"


@dataclass
class CompletionResult:
    """Result of a non-streaming completion."""
    text: str = ""
    tool_calls: list[CanonicalToolCall] = field(default_factory=list)
    stop_reason: str = ""  # "end_turn" | "tool_use" | "max_tokens"
