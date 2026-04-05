"""Chat endpoint - text in, streamed text out, with session persistence."""

from __future__ import annotations

import logging

from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse, Response

from app.services import claude_service, tts_service
from app.services.session_service import load_session, save_session, list_sessions, consolidate_session
from app.services.response_digest import digest_for_speech

logger = logging.getLogger("tuesday.chat")

router = APIRouter()


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class Attachment(BaseModel):
    """A document/image content block from /documents/upload."""
    type: str  # "image", "document", "text"
    source: dict | None = None  # For image/document blocks
    text: str | None = None     # For text blocks


class ChatRequest(BaseModel):
    messages: list[Message]
    session_id: str | None = None
    attachments: list[Attachment] | None = None  # Files to include with the latest message


class SpeakRequest(BaseModel):
    text: str


@router.post("/chat")
async def chat(request: Request, body: ChatRequest, background_tasks: BackgroundTasks):
    """Stream a response from Tuesday via Server-Sent Events."""
    messages = [m.model_dump() for m in body.messages]
    session_id = body.session_id

    # If attachments present, convert the last user message to multimodal content
    if body.attachments and messages:
        last_msg = messages[-1]
        if last_msg["role"] == "user" and isinstance(last_msg["content"], str):
            content_blocks = [att.model_dump(exclude_none=True) for att in body.attachments]
            content_blocks.append({"type": "text", "text": last_msg["content"]})
            messages[-1] = {"role": "user", "content": content_blocks}

    async def event_generator():
        nonlocal messages

        # Surface any pending self-diagnosis notifications
        try:
            from app.services.diagnosis_service import get_pending_notifications, clear_notifications
            notifications = get_pending_notifications()
            if notifications:
                for n in notifications:
                    yield {
                        "event": "tool_status",
                        "data": f"Self-diagnosis: found issue with {n['tool_name']} — {n['root_cause'][:100]}. Issue created on GitHub.",
                    }
                clear_notifications()
        except Exception:
            pass

        # Auto-consolidate if session is too long
        if session_id:
            messages, consolidated = await consolidate_session(session_id, messages)
            if consolidated:
                yield {"event": "tool_status", "data": "Consolidating memory..."}

        full_response = ""
        async for event in claude_service.chat(messages):
            if await request.is_disconnected():
                break
            if event["type"] == "text":
                yield {"event": "token", "data": event["data"]}
                full_response += event["data"]
            elif event["type"] == "tool_status":
                yield {"event": "tool_status", "data": event["data"]}
            elif event["type"] == "done":
                yield {"event": "done", "data": ""}

        # Save session in background (use consolidated messages, not originals)
        if session_id and full_response:
            save_messages = list(messages)
            save_messages.append({"role": "assistant", "content": full_response})
            background_tasks.add_task(save_session, session_id, save_messages)

            # Run metacognitive pass in background (pattern extraction)
            from app.services.metacognition_service import run_metacognitive_pass
            background_tasks.add_task(run_metacognitive_pass, session_id, save_messages)

    return EventSourceResponse(event_generator())


@router.post("/chat/sync")
async def chat_sync(body: ChatRequest) -> dict:
    """Non-streaming chat endpoint."""
    messages = [m.model_dump() for m in body.messages]
    chunks: list[str] = []
    async for event in claude_service.chat(messages):
        if event["type"] == "text":
            chunks.append(event["data"])
    return {"response": "".join(chunks)}


@router.get("/sessions")
async def get_sessions(limit: int = 10):
    """List recent sessions."""
    sessions = await list_sessions(limit=limit)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Load a specific session."""
    data = await load_session(session_id)
    if data is None:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    return data


@router.post("/chat/speak")
async def speak(body: SpeakRequest):
    """Convert text to speech audio. Text is digested for natural speech first."""
    from app.config import settings

    if not settings.elevenlabs_api_key and settings.tts_provider == "elevenlabs":
        logger.warning("TTS requested but ELEVENLABS_API_KEY not set")
        return JSONResponse(status_code=503, content={"error": "ElevenLabs API key not configured"})

    # Clean text for speech: expand abbreviations, strip markdown, truncate
    speech_text = digest_for_speech(body.text)
    logger.info(f"TTS digest: {len(body.text)} chars -> {len(speech_text)} chars")

    try:
        audio_chunks: list[bytes] = []
        async for chunk in tts_service.text_to_speech(speech_text):
            audio_chunks.append(chunk)

        audio_bytes = b"".join(audio_chunks)

        if len(audio_bytes) < 200:
            logger.warning(f"TTS returned suspiciously small audio ({len(audio_bytes)} bytes)")
            return JSONResponse(status_code=502, content={"error": "TTS returned empty audio"})

        logger.info(f"TTS success: {len(audio_bytes)} bytes for {len(speech_text)} chars")
        return Response(content=audio_bytes, media_type="audio/mpeg")

    except Exception as e:
        logger.error(f"TTS failed: {e}")
        return JSONResponse(status_code=503, content={"error": f"TTS failed: {str(e)}"})
