from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: os.environ["ANTHROPIC_API_KEY"])
    model: str = os.getenv("TUESDAY_MODEL", "claude-sonnet-4-6")
    max_tokens: int = int(os.getenv("TUESDAY_MAX_TOKENS", "4096"))

    # TTS
    tts_provider: str = os.getenv("TUESDAY_TTS_PROVIDER", "elevenlabs")
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    voice_id: str = os.getenv("TUESDAY_VOICE_ID", "pNInz6obpgDQGcFmaJgB")  # "Adam" - deep male

    # Web search
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "")

    # GitHub
    github_token: str = os.getenv("GITHUB_TOKEN", "")

    # Auth
    tuesday_auth_token: str = os.getenv("TUESDAY_AUTH_TOKEN", "")
    environment: str = os.getenv("TUESDAY_ENV", "dev")

    # Session consolidation
    consolidation_message_threshold: int = int(os.getenv("TUESDAY_CONSOLIDATION_MESSAGES", "50"))
    consolidation_keep_recent: int = int(os.getenv("TUESDAY_KEEP_RECENT", "20"))

    # Paths
    knowledge_dir: Path = KNOWLEDGE_DIR
    sessions_dir: Path = Path(__file__).resolve().parents[1] / "sessions"
    logs_dir: Path = Path(__file__).resolve().parents[1] / "logs"


settings = Settings()
