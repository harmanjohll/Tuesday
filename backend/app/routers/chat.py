"""Chat endpoint - text in, streamed text out, with session persistence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta

import anthropic
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse, Response

from app.config import settings
from app.services import claude_service, tts_service
from app.services.session_service import load_session, save_session, list_sessions, consolidate_session
from app.services.response_digest import digest_for_speech

logger = logging.getLogger("tuesday.chat")

SGT = timezone(timedelta(hours=8))

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


@router.post("/session-start")
async def session_start():
    """Proactive context-aware greeting when Harman opens Tuesday.

    Gathers environment context (time, agents, calendar, emails, follow-ups)
    and synthesizes a brief, natural greeting. Conserves tokens: if nothing
    is pending, returns a static greeting with zero API cost.
    """
    context_parts: list[str] = []

    now = datetime.now(SGT)
    hour = now.hour
    time_context = (
        "early morning" if hour < 7
        else "morning" if hour < 12
        else "afternoon" if hour < 17
        else "evening" if hour < 21
        else "late night"
    )

    # Check agent statuses
    try:
        from app.services.agent_service import get_all_agents_status
        agent_updates = get_all_agents_status()
        if agent_updates:
            context_parts.append(f"Agent updates: {json.dumps(agent_updates)}")
    except Exception as e:
        logger.debug(f"Session-start: agents check failed: {e}")

    # Check calendar (next 4 hours)
    try:
        from app.services import gcalendar_service
        events = await gcalendar_service.list_events({"hours_ahead": 4})
        if events and "no events" not in events.lower() and "not connected" not in events.lower():
            context_parts.append(f"Upcoming calendar: {events}")
    except Exception as e:
        logger.debug(f"Session-start: calendar check failed: {e}")

    # Check follow-ups due soon
    try:
        from app.tools.executor import _check_followups
        followups = await _check_followups({"days_ahead": 1})
        if "No follow-ups" not in followups:
            context_parts.append(f"Follow-ups: {followups}")
    except Exception as e:
        logger.debug(f"Session-start: follow-ups check failed: {e}")

    # Check unread emails (quick count)
    try:
        from app.services import gmail_service
        emails = await gmail_service.get_messages({"unread_only": True, "max_results": 5})
        if "not connected" not in emails.lower() and "not configured" not in emails.lower():
            context_parts.append(f"Email: {emails}")
    except Exception as e:
        logger.debug(f"Session-start: email check failed: {e}")

    # No context → static greeting (zero tokens)
    if not context_parts:
        greetings = {
            "early morning": "You're up early. What's on your mind?",
            "morning": "Good morning, Harman.",
            "afternoon": "Good afternoon, Harman.",
            "evening": "Good evening, Harman.",
            "late night": "Burning the midnight oil?",
        }
        return {"content": greetings.get(time_context, "Hey, Harman."), "has_context": False}

    # Synthesize with Claude — brief, warm, natural
    context_block = "\n".join(context_parts)
    prompt = (
        f"You are Tuesday, Harman's AI assistant. It's {time_context} in Singapore "
        f"({now.strftime('%I:%M %p')}). Harman just opened you. Here's what's pending:\n\n"
        f"{context_block}\n\n"
        f"Give a brief, warm, natural greeting that surfaces the most important 1-2 items. "
        f"Max 80 words. Don't list everything — prioritize. Sound like a trusted aide, not a dashboard. "
        f"No markdown. No bullet points."
    )

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.model,
            max_tokens=settings.session_start_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"content": response.content[0].text, "has_context": True}
    except Exception as e:
        logger.error(f"Session-start Claude call failed: {e}")
        return {"content": f"Good {time_context}, Harman.", "has_context": False}
