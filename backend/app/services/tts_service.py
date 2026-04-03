"""Text-to-speech service for Tuesday's voice."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.config import settings


async def text_to_speech(text: str) -> AsyncIterator[bytes]:
    """Convert text to speech audio bytes.

    Returns audio chunks as they become available for streaming playback.
    Currently a stub - will integrate with ElevenLabs or OpenAI TTS.
    """
    if settings.tts_provider == "elevenlabs":
        async for chunk in _elevenlabs_tts(text):
            yield chunk
    elif settings.tts_provider == "openai":
        async for chunk in _openai_tts(text):
            yield chunk
    else:
        raise ValueError(f"Unknown TTS provider: {settings.tts_provider}")


async def _elevenlabs_tts(text: str) -> AsyncIterator[bytes]:
    """ElevenLabs TTS integration.

    Requires: ELEVENLABS_API_KEY and TUESDAY_VOICE_ID in env.
    """
    import httpx

    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY not set in .env")
    if not settings.voice_id:
        raise ValueError("TUESDAY_VOICE_ID not set in .env")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.voice_id}/stream"
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(1024):
                yield chunk


async def _openai_tts(text: str) -> AsyncIterator[bytes]:
    """OpenAI TTS integration.

    Requires: OPENAI_API_KEY in env.
    Install: pip install tuesday[tts]
    """
    import httpx

    url = "https://api.openai.com/v1/audio/speech"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    payload = {
        "model": "tts-1",
        "voice": settings.voice_id or "onyx",
        "input": text,
        "response_format": "opus",
    }

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(1024):
                yield chunk
