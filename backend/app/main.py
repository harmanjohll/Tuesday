"""Tuesday - Personal AI Assistant backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, voice
from app.services.claude_service import reload_system_prompt
from app.config import settings

app = FastAPI(
    title="Tuesday",
    description="Personal AI Assistant API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, tags=["chat"])
app.include_router(voice.router, tags=["voice"])


@app.on_event("startup")
async def startup():
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "online", "assistant": "Tuesday"}


@app.post("/reload-knowledge")
async def reload_knowledge():
    """Reload knowledge files without restarting the server."""
    prompt = reload_system_prompt()
    return {"status": "reloaded", "prompt_length": len(prompt)}
