"""Tuesday - Personal AI Assistant backend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import chat, voice, auth_outlook, auth_gmail, documents, briefing, agents
from app.services.claude_service import reload_system_prompt
from app.middleware.auth import AuthMiddleware
from app.config import settings

app = FastAPI(
    title="Tuesday",
    description="Personal AI Assistant API",
    version="0.2.0",
)

# Auth middleware (active only when TUESDAY_AUTH_TOKEN is set)
app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, tags=["chat"])
app.include_router(voice.router, tags=["voice"])
app.include_router(auth_outlook.router)
app.include_router(auth_gmail.router)
app.include_router(documents.router)
app.include_router(briefing.router)
app.include_router(agents.router)


@app.on_event("startup")
async def startup():
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.agents_dir.mkdir(parents=True, exist_ok=True)
    settings.templates_dir.mkdir(parents=True, exist_ok=True)

    # Start background scheduler (morning briefings, etc.)
    from app.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    from app.scheduler import stop_scheduler
    stop_scheduler()


@app.get("/health")
async def health():
    return {
        "status": "online",
        "assistant": "Tuesday",
        "auth": "enabled" if settings.tuesday_auth_token else "disabled",
        "github": "configured" if settings.github_token else "not configured",
        "search": "configured" if settings.brave_search_api_key else "not configured",
        "outlook": "configured" if settings.microsoft_client_id else "not configured",
        "gmail": "configured" if settings.google_client_id else "not configured",
    }


@app.post("/reload-knowledge")
async def reload_knowledge():
    """Reload knowledge files without restarting the server."""
    prompt = reload_system_prompt()
    return {"status": "reloaded", "prompt_length": len(prompt)}


# In production, serve the built frontend from FastAPI.
# The frontend build output goes to ../frontend/dist/
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
