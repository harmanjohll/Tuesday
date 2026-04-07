"""Anthropic (Claude) model adapter."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator
from uuid import uuid4

from anthropic import AsyncAnthropic

from app.config import settings
from app.adapters.base import ModelAdapter
from app.adapters.types import (
    CanonicalMessage,
    CanonicalToolCall,
    CanonicalToolDef,
    CompletionResult,
    StreamEvent,
)

logger = logging.getLogger("tuesday.adapters.anthropic")


class AnthropicAdapter(ModelAdapter):

    def __init__(self):
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # --- Format translation ---

    def _to_anthropic_tools(self, tools: list[CanonicalToolDef]) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]

    def _to_anthropic_messages(self, messages: list[CanonicalMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.role == "tool_results":
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tr.tool_call_id,
                            "content": tr.content,
                        }
                        for tr in msg.tool_results
                    ],
                })
            elif msg.role == "assistant" and msg.tool_calls:
                content: list[dict] = []
                if msg.text:
                    content.append({"type": "text", "text": msg.text})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                result.append({"role": "assistant", "content": content})
            else:
                result.append({"role": msg.role, "content": msg.text})
        return result

    # --- Non-streaming ---

    async def complete(
        self,
        model: str,
        system_prompt: str,
        messages: list[CanonicalMessage],
        tools: list[CanonicalToolDef],
        max_tokens: int,
    ) -> CompletionResult:
        anthropic_tools = self._to_anthropic_tools(tools)
        anthropic_msgs = self._to_anthropic_messages(messages)

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": anthropic_msgs,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self._client.messages.create(**kwargs)

        text = ""
        tool_calls: list[CanonicalToolCall] = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(CanonicalToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        return CompletionResult(
            text=text,
            tool_calls=tool_calls,
            stop_reason="tool_use" if response.stop_reason == "tool_use" else "end_turn",
        )

    # --- Streaming ---

    async def stream(
        self,
        model: str,
        system_prompt: str,
        messages: list[CanonicalMessage],
        tools: list[CanonicalToolDef],
        max_tokens: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        anthropic_tools = self._to_anthropic_tools(tools)
        anthropic_msgs = self._to_anthropic_messages(messages)

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": anthropic_msgs,
            "stream": True,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await self._client.messages.create(**kwargs)

        current_tool_use: dict | None = None
        current_tool_input_json = ""
        stop_reason = "end_turn"

        async for event in response:
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "text":
                    if block.text:
                        yield StreamEvent(type="text_delta", text=block.text)
                elif block.type == "tool_use":
                    current_tool_use = {"id": block.id, "name": block.name}
                    current_tool_input_json = ""

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield StreamEvent(type="text_delta", text=delta.text)
                elif delta.type == "input_json_delta":
                    current_tool_input_json += delta.partial_json

            elif event.type == "content_block_stop":
                if current_tool_use is not None:
                    try:
                        args = json.loads(current_tool_input_json) if current_tool_input_json else {}
                    except json.JSONDecodeError:
                        args = {}
                    yield StreamEvent(
                        type="tool_call_end",
                        tool_call=CanonicalToolCall(
                            id=current_tool_use["id"],
                            name=current_tool_use["name"],
                            arguments=args,
                        ),
                    )
                    current_tool_use = None
                    current_tool_input_json = ""

            elif event.type == "message_delta":
                stop_reason = event.delta.stop_reason or "end_turn"

        yield StreamEvent(type="done", stop_reason=stop_reason)
