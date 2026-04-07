"""Google Gemini model adapter.

Uses the google.genai unified SDK (2026+). Translates between
canonical types and Gemini's Content/Part/FunctionCall format.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator
from uuid import uuid4

from app.config import settings
from app.adapters.base import ModelAdapter
from app.adapters.types import (
    CanonicalMessage,
    CanonicalToolCall,
    CanonicalToolDef,
    CompletionResult,
    StreamEvent,
)

logger = logging.getLogger("tuesday.adapters.gemini")


class GeminiAdapter(ModelAdapter):

    def __init__(self):
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Required for agents using Gemini models."
            )
        from google import genai
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._genai_types = None  # Lazy import

    @property
    def _types(self):
        if self._genai_types is None:
            from google.genai import types
            self._genai_types = types
        return self._genai_types

    # --- Format translation ---

    def _to_gemini_tools(self, tools: list[CanonicalToolDef]) -> list | None:
        if not tools:
            return None
        types = self._types
        declarations = []
        for t in tools:
            # Clean parameters for Gemini — remove unsupported JSON Schema keys
            params = _clean_schema_for_gemini(t.parameters) if t.parameters else None
            declarations.append(types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=params,
            ))
        return [types.Tool(function_declarations=declarations)]

    def _to_gemini_contents(
        self, messages: list[CanonicalMessage],
    ) -> list:
        types = self._types
        contents = []
        for msg in messages:
            if msg.role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.text)],
                ))
            elif msg.role == "assistant":
                parts = []
                if msg.text:
                    parts.append(types.Part.from_text(text=msg.text))
                for tc in msg.tool_calls:
                    parts.append(types.Part.from_function_call(
                        name=tc.name,
                        args=tc.arguments,
                    ))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool_results":
                parts = []
                for tr in msg.tool_results:
                    parts.append(types.Part.from_function_response(
                        name=tr.name,
                        response={"result": tr.content},
                    ))
                if parts:
                    contents.append(types.Content(role="user", parts=parts))
        return contents

    def _build_config(
        self, system_prompt: str, tools: list[CanonicalToolDef], max_tokens: int,
    ):
        types = self._types
        gemini_tools = self._to_gemini_tools(tools)
        kwargs: dict = {
            "system_instruction": system_prompt,
            "max_output_tokens": max_tokens,
        }
        if gemini_tools:
            kwargs["tools"] = gemini_tools
        return types.GenerateContentConfig(**kwargs)

    # --- Non-streaming ---

    async def complete(
        self,
        model: str,
        system_prompt: str,
        messages: list[CanonicalMessage],
        tools: list[CanonicalToolDef],
        max_tokens: int,
    ) -> CompletionResult:
        contents = self._to_gemini_contents(messages)
        config = self._build_config(system_prompt, tools, max_tokens)

        response = await self._client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        text = ""
        tool_calls: list[CanonicalToolCall] = []

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text += part.text
                elif part.function_call:
                    tool_calls.append(CanonicalToolCall(
                        id=uuid4().hex[:12],
                        name=part.function_call.name,
                        arguments=dict(part.function_call.args) if part.function_call.args else {},
                    ))

        # Map finish reason
        stop_reason = "end_turn"
        if tool_calls:
            stop_reason = "tool_use"
        elif response.candidates:
            fr = response.candidates[0].finish_reason
            if fr and "MAX_TOKENS" in str(fr):
                stop_reason = "max_tokens"

        return CompletionResult(text=text, tool_calls=tool_calls, stop_reason=stop_reason)

    # --- Streaming ---

    async def stream(
        self,
        model: str,
        system_prompt: str,
        messages: list[CanonicalMessage],
        tools: list[CanonicalToolDef],
        max_tokens: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        contents = self._to_gemini_contents(messages)
        config = self._build_config(system_prompt, tools, max_tokens)

        has_tool_calls = False

        async for chunk in await self._client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            if not chunk.candidates:
                continue
            candidate = chunk.candidates[0]
            if not candidate.content or not candidate.content.parts:
                continue

            for part in candidate.content.parts:
                if part.text:
                    yield StreamEvent(type="text_delta", text=part.text)
                elif part.function_call:
                    has_tool_calls = True
                    yield StreamEvent(
                        type="tool_call_end",
                        tool_call=CanonicalToolCall(
                            id=uuid4().hex[:12],
                            name=part.function_call.name,
                            arguments=dict(part.function_call.args) if part.function_call.args else {},
                        ),
                    )

        yield StreamEvent(
            type="done",
            stop_reason="tool_use" if has_tool_calls else "end_turn",
        )


def _clean_schema_for_gemini(schema: dict) -> dict:
    """Remove JSON Schema keys that Gemini doesn't support.

    Gemini's function calling uses a subset of OpenAPI schema.
    Keys like 'additionalProperties', 'default', '$schema' cause errors.
    """
    if not isinstance(schema, dict):
        return schema

    cleaned = {}
    skip_keys = {"additionalProperties", "default", "$schema", "examples", "title"}
    for key, value in schema.items():
        if key in skip_keys:
            continue
        if isinstance(value, dict):
            cleaned[key] = _clean_schema_for_gemini(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _clean_schema_for_gemini(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned
