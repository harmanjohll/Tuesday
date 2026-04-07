"""Model adapter registry — resolves the correct adapter for a model string."""

from __future__ import annotations

from app.adapters.base import ModelAdapter

_adapters: dict[str, ModelAdapter] = {}


def get_adapter(model: str) -> ModelAdapter:
    """Resolve the correct adapter from a model name.

    Examples:
        get_adapter("claude-sonnet-4-6")  -> AnthropicAdapter
        get_adapter("gemini-2.5-flash")   -> GeminiAdapter
    """
    if model.startswith("gemini"):
        provider = "gemini"
    else:
        provider = "anthropic"

    if provider not in _adapters:
        if provider == "anthropic":
            from .anthropic_adapter import AnthropicAdapter
            _adapters[provider] = AnthropicAdapter()
        elif provider == "gemini":
            from .gemini_adapter import GeminiAdapter
            _adapters[provider] = GeminiAdapter()

    return _adapters[provider]
