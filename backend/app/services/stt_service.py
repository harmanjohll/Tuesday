"""Speech-to-text service for Tuesday's voice input."""

from __future__ import annotations

from app.config import settings


async def speech_to_text(audio_bytes: bytes, content_type: str = "audio/webm") -> str:
    """Convert speech audio to text.

    Accepts audio bytes (from browser MediaRecorder) and returns transcript text.
    Currently uses OpenAI Whisper API. Deepgram is an alternative for lower latency.
    """
    import httpx

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    # Map content types to file extensions for the API
    ext_map = {
        "audio/webm": "webm",
        "audio/wav": "wav",
        "audio/mp4": "m4a",
        "audio/ogg": "ogg",
    }
    ext = ext_map.get(content_type, "webm")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers=headers,
            files={"file": (f"audio.{ext}", audio_bytes, content_type)},
            data={"model": "whisper-1", "response_format": "text"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.text.strip()
