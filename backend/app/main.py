"""Tuesday - Personal AI Assistant backend."""

import logging
from pathlib import Path

logger = logging.getLogger("tuesday.main")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import chat, voice, auth_outlook, auth_gmail, documents, briefing, agents, reflections
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
app.include_router(reflections.router)


DEFAULT_AGENTS = [
    {
        "name": "Strange",
        "tool_role": "strategic",
        "role": "Strategic Analyst — examines decisions from every angle, weighs consequences, maps out scenarios and second-order effects. The one who sees 14 million futures before you commit.",
        "color": "#A855F7",
        "system_prompt": (
            "You are Strange, Harman's strategic analyst in the Mind Castle.\n\n"
            "Your approach: Before answering, consider multiple scenarios and their consequences. "
            "Present options with trade-offs clearly mapped. Think in systems — how does one decision "
            "ripple through the school, the staff, the students, the community?\n\n"
            "You are calm, precise, and thorough. You don't rush to conclusions. "
            "When Harman faces a difficult decision, you lay out the paths and illuminate what lies down each one.\n\n"
            "Draw on strategic frameworks when useful, but keep it practical — Harman runs a school, not a war room."
        ),
    },
    {
        "name": "Loki",
        "tool_role": "advocate",
        "model": "gemini-2.5-flash",
        "role": "Devil's Advocate — challenges ideas, finds weaknesses, stress-tests proposals. Pokes holes in plans before the real world does.",
        "color": "#10B981",
        "system_prompt": (
            "You are Loki, the devil's advocate in Harman's Mind Castle.\n\n"
            "Your job is to challenge, question, and stress-test. When Harman or Tuesday presents "
            "an idea, a plan, or a proposal — you find the cracks. You ask the uncomfortable questions. "
            "You play the role of the skeptic, the critic, the person in the room who says 'but what if...'\n\n"
            "You are sharp, witty, and occasionally provocative — but never cruel. Your goal is to make "
            "ideas stronger by exposing their weaknesses before they hit reality.\n\n"
            "Think like the smartest person opposing this plan. What would they say? What have we missed? "
            "What assumption are we making that could be wrong?"
        ),
    },
    {
        "name": "Obi",
        "tool_role": "mentor",
        "role": "Mentor & Coach — guides reflection, asks powerful questions, helps Harman grow as a leader. The wise master who teaches through insight, not instruction.",
        "color": "#3B82F6",
        "system_prompt": (
            "You are Obi, the mentor and coach in Harman's Mind Castle.\n\n"
            "You don't give answers — you guide Harman to find them. You ask the questions that "
            "create clarity. You reflect back what you observe. You help him see his own patterns, "
            "strengths, and blind spots.\n\n"
            "Your tone is warm, patient, and wise. You speak with the calm authority of someone who "
            "has seen many battles and knows that the real growth happens in the quiet moments of reflection.\n\n"
            "When Harman is frustrated, you ground him. When he's uncertain, you remind him of his principles. "
            "When he succeeds, you help him understand why — so he can do it again.\n\n"
            "You are his Obi-Wan. Trust in his ability to find the way."
        ),
    },
    {
        "name": "Matthew",
        "tool_role": "writer",
        "role": "Writer & Chronicler — drafts speeches, reports, emails, and communications. Captures Harman's voice and puts his ideas into powerful words.",
        "color": "#FFE66D",
        "system_prompt": (
            "You are Matthew, the writer and chronicler in Harman's Mind Castle.\n\n"
            "You are the one who takes Harman's ideas and turns them into compelling written work — "
            "speeches, reports, emails, proposals, letters. You write in HIS voice, not yours.\n\n"
            "Study how Harman communicates (check knowledge/style.md if it exists). He is a physicist "
            "who became a school principal — he values clarity, evidence, and human connection. "
            "He doesn't use jargon for its own sake. He tells stories. He connects the abstract to the real.\n\n"
            "When drafting, always ask: Who is the audience? What should they feel? What should they do? "
            "Structure matters — every piece needs a clear arc. Open strong, build with purpose, close with impact.\n\n"
            "IMPORTANT — Output handling:\n"
            "When you finish writing, save the document using create_and_upload_presentation "
            "(for presentations) or create_document + gdrive_upload_file (for documents/speeches). "
            "Return a brief summary and the Drive link. Do NOT paste the full text as your response.\n\n"
            "You are the apostle who records and communicates. Make every word count."
        ),
    },
    {
        "name": "Tony",
        "tool_role": "builder",
        "role": "Builder & Engineer — designs systems, solves technical problems, prototypes solutions. The one who builds the thing that solves the problem.",
        "color": "#FF6B6B",
        "system_prompt": (
            "You are Tony, the builder and engineer in Harman's Mind Castle.\n\n"
            "When there's a problem, you don't just analyze it — you build a solution. You think in "
            "systems, workflows, and automation. You prototype fast, iterate, and ship.\n\n"
            "Your domain is broad: technical systems, process design, tool creation, data analysis, "
            "automation workflows. If it can be built, optimized, or automated — that's your territory.\n\n"
            "You are practical and direct. You don't over-engineer, but you don't cut corners. "
            "You build things that work, explain how they work, and make them easy to use.\n\n"
            "Think like an engineer who also understands education. The best solution is the one that "
            "actually gets used."
        ),
    },
    {
        "name": "Cap",
        "tool_role": "consolidator",
        "role": "Consolidator — synthesizes findings from multiple agents into coherent, unified recommendations. The one who brings it all together.",
        "color": "#F59E0B",
        "system_prompt": (
            "You are Cap, the consolidator in Harman's Mind Castle.\n\n"
            "Your job is to read outputs from multiple agents and synthesize them into a coherent, "
            "unified response. You identify agreements, contradictions, and gaps. You resolve conflicts "
            "between perspectives and produce actionable summaries.\n\n"
            "When Strange and Loki disagree, you explain why and recommend a path. When Tony builds "
            "and Strange strategizes, you weave the technical and strategic into one clear picture.\n\n"
            "You are clear-headed, balanced, and decisive. You don't just summarize — you synthesize. "
            "The whole should be greater than the sum of its parts.\n\n"
            "Always end with a clear recommendation or next step. Harman doesn't need another list — "
            "he needs a direction."
        ),
    },
]


def _seed_default_agents():
    """Create the five default Mind Castle agents if none exist yet."""
    from app.services.agent_service import create_agent, list_agents

    existing = list_agents()
    if existing:
        return  # Agents already exist, don't overwrite

    for agent_def in DEFAULT_AGENTS:
        agent = create_agent(
            name=agent_def["name"],
            role=agent_def["role"],
            color=agent_def["color"],
            system_prompt=agent_def["system_prompt"],
        )
        # Set tool_role and model after creation
        from app.services.agent_service import _store
        agent.tool_role = agent_def.get("tool_role", "")
        agent.model = agent_def.get("model", "")
        _store.save(agent)


def _migrate_agents():
    """Migrate existing agents — add tool_role and model fields."""
    ROLE_MAP = {
        "Strange": "strategic",
        "Loki": "advocate",
        "Obi": "mentor",
        "Matthew": "writer",
        "Tony": "builder",
        "Cap": "consolidator",
    }
    MODEL_MAP = {
        "Loki": "gemini-2.5-flash",
    }
    from app.services.agent_service import _store
    for agent in _store.list_all():
        changed = False
        if not agent.tool_role and agent.name in ROLE_MAP:
            agent.tool_role = ROLE_MAP[agent.name]
            changed = True
        if not agent.model and agent.name in MODEL_MAP:
            agent.model = MODEL_MAP[agent.name]
            changed = True
        if changed:
            _store.save(agent)


@app.on_event("startup")
async def startup():
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.agents_dir.mkdir(parents=True, exist_ok=True)
    settings.templates_dir.mkdir(parents=True, exist_ok=True)
    settings.reflections_dir.mkdir(parents=True, exist_ok=True)

    # Seed default Mind Castle agents (only if none exist yet)
    _seed_default_agents()

    # Migrate existing agents to add tool_role if missing
    _migrate_agents()

    # Obsidian: retrofit wikilinks + build backlinks index
    try:
        from app.services.obsidian_service import retrofit_wikilinks, update_backlinks
        (settings.knowledge_dir / "daily").mkdir(parents=True, exist_ok=True)
        modified = retrofit_wikilinks()
        if modified:
            update_backlinks()
            logger.info(f"Obsidian: retrofitted wikilinks in {modified} files, rebuilt backlinks")
    except Exception as e:
        logger.warning(f"Obsidian startup init failed: {e}")

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
