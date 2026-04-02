"""Voice endpoint - audio in, audio out."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile
from starlette.responses import StreamingResponse

from app.services import claude_service, stt_service, tts_service

router = APIRouter()


@router.post("/voice")
async def voice(audio: UploadFile):
    """Full voice pipeline: speech -> text -> Claude -> text -> speech.

    Accepts audio file upload from browser, returns audio stream of Tuesday's response.
    """
    # 1. Speech to text
    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"
    transcript = await stt_service.speech_to_text(audio_bytes, content_type)

    # 2. Get response from Claude
    messages = [{"role": "user", "content": transcript}]
    chunks: list[str] = []
    async for chunk in claude_service.chat(messages):
        chunks.append(chunk)
    response_text = "".join(chunks)

    # 3. Text to speech
    return StreamingResponse(
        tts_service.text_to_speech(response_text),
        media_type="audio/mpeg",
        headers={"X-Transcript": transcript, "X-Response-Text": response_text[:500]},
    )


@router.post("/voice/transcribe")
async def transcribe(audio: UploadFile) -> dict:
    """Transcribe audio to text only (no Claude response)."""
    audio_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"
    transcript = await stt_service.speech_to_text(audio_bytes, content_type)
    return {"transcript": transcript}
