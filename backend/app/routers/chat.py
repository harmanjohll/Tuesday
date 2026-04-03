"""Chat endpoint - text in, streamed text out."""

from __future__ import annotations

from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request
from starlette.responses import StreamingResponse

from fastapi import APIRouter

from app.services import claude_service, tts_service

router = APIRouter()


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class SpeakRequest(BaseModel):
    text: str


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """Stream a response from Tuesday via Server-Sent Events."""
    messages = [m.model_dump() for m in body.messages]

    async def event_generator():
        async for chunk in claude_service.chat(messages):
            # Check if client disconnected
            if await request.is_disconnected():
                break
            yield {"event": "token", "data": chunk}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


@router.post("/chat/sync")
async def chat_sync(body: ChatRequest) -> dict:
    """Non-streaming chat endpoint. Returns full response at once.
    Useful for voice pipeline where we need the full text for TTS.
    """
    messages = [m.model_dump() for m in body.messages]
    chunks: list[str] = []
    async for chunk in claude_service.chat(messages):
        chunks.append(chunk)
    return {"response": "".join(chunks)}


@router.post("/chat/speak")
async def speak(body: SpeakRequest):
    """Convert text to speech audio. Send Tuesday's response text, get audio back."""
    return StreamingResponse(
        tts_service.text_to_speech(body.text),
        media_type="audio/mpeg",
    )
