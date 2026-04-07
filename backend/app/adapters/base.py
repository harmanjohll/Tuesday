"""Abstract model adapter — the contract every provider must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.adapters.types import (
    CanonicalMessage,
    CanonicalToolDef,
    CompletionResult,
    StreamEvent,
)


class ModelAdapter(ABC):
    """Interface for LLM provider adapters.

    Each adapter translates between the canonical types used by
    agent_service and the native SDK format of its provider.
    """

    @abstractmethod
    async def complete(
        self,
        model: str,
        system_prompt: str,
        messages: list[CanonicalMessage],
        tools: list[CanonicalToolDef],
        max_tokens: int,
    ) -> CompletionResult:
        """Non-streaming completion (background tasks)."""
        ...

    @abstractmethod
    async def stream(
        self,
        model: str,
        system_prompt: str,
        messages: list[CanonicalMessage],
        tools: list[CanonicalToolDef],
        max_tokens: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Streaming completion (interactive chat)."""
        ...
