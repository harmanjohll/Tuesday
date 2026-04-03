"""Chat endpoint - text in, streamed text out."""

from __future__ import annotations

import logging

from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.services import claude_service, tts_service

logger = logging.getLogger("tuesday.chat")

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
            if await request.is_disconnected():
                break
            yield {"event": "token", "data": chunk}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())


@router.post("/chat/sync")
async def chat_sync(body: ChatRequest) -> dict:
    """Non-streaming chat endpoint."""
    messages = [m.model_dump() for m in body.messages]
    chunks: list[str] = []
    async for chunk in claude_service.chat(messages):
        chunks.append(chunk)
    return {"response": "".join(chunks)}


@router.post("/chat/speak")
async def speak(body: SpeakRequest):
    """Convert text to speech audio.

    Buffers the full audio from ElevenLabs before responding.
    This avoids the problem where StreamingResponse sends 200 headers
    before the generator encounters an error mid-stream.
    """
    from app.config import settings

    if not settings.elevenlabs_api_key and settings.tts_provider == "elevenlabs":
        logger.warning("TTS requested but ELEVENLABS_API_KEY not set")
        return JSONResponse(status_code=503, content={"error": "ElevenLabs API key not configured"})

    try:
        # Buffer the full response — catches errors before sending anything to client
        audio_chunks: list[bytes] = []
        async for chunk in tts_service.text_to_speech(body.text):
            audio_chunks.append(chunk)

        audio_bytes = b"".join(audio_chunks)

        if len(audio_bytes) < 200:
            logger.warning(f"TTS returned suspiciously small audio ({len(audio_bytes)} bytes)")
            return JSONResponse(status_code=502, content={"error": "TTS returned empty audio"})

        logger.info(f"TTS success: {len(audio_bytes)} bytes for {len(body.text)} chars")
        return Response(content=audio_bytes, media_type="audio/mpeg")

    except Exception as e:
        logger.error(f"TTS failed: {e}")
        return JSONResponse(status_code=503, content={"error": f"TTS failed: {str(e)}"})
