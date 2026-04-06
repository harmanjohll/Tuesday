"""Tuesday - Personal AI Assistant backend."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import chat, voice, auth_outlook, auth_gmail, documents, briefing, agents, activity
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
app.include_router(activity.router)


DEFAULT_AGENTS = [
    {
        "name": "Strange",
        "role": "Strategic Analyst — examines decisions from every angle, weighs consequences, maps out scenarios and second-order effects. The one who sees 14 million futures before you commit.",
        "color": "#A855F7",
        "specialty": "Strategic Analysis",
        "skills": ["scenario_planning.md", "decision_matrices.md"],
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
        "role": "Devil's Advocate — challenges ideas, finds weaknesses, stress-tests proposals. Pokes holes in plans before the real world does.",
        "color": "#10B981",
        "specialty": "Devil's Advocate",
        "skills": ["critical_analysis.md"],
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
        "role": "Mentor & Coach — guides reflection, asks powerful questions, helps Harman grow as a leader. The wise master who teaches through insight, not instruction.",
        "color": "#3B82F6",
        "specialty": "Mentoring & Coaching",
        "skills": ["coaching_models.md", "reflective_practice.md"],
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
        "role": "Writer & Chronicler — drafts speeches, reports, emails, and communications. Captures Harman's voice and puts his ideas into powerful words.",
        "color": "#FFE66D",
        "specialty": "Writing & Speeches",
        "skills": ["speech_writing.md", "persuasive_frameworks.md"],
        "system_prompt": (
            "You are Matthew, the writer and chronicler in Harman's Mind Castle.\n\n"
            "You are the one who takes Harman's ideas and turns them into compelling written work — "
            "speeches, reports, emails, proposals, letters. You write in HIS voice, not yours.\n\n"
            "Study how Harman communicates (check knowledge/style.md if it exists). He is a physicist "
            "who became a school principal — he values clarity, evidence, and human connection. "
            "He doesn't use jargon for its own sake. He tells stories. He connects the abstract to the real.\n\n"
            "When drafting, always ask: Who is the audience? What should they feel? What should they do? "
            "Structure matters — every piece needs a clear arc. Open strong, build with purpose, close with impact.\n\n"
            "You are the apostle who records and communicates. Make every word count."
        ),
    },
    {
        "name": "Tony",
        "role": "Builder & Engineer — designs systems, solves technical problems, prototypes solutions. The one who builds the thing that solves the problem.",
        "color": "#FF6B6B",
        "specialty": "Systems & Engineering",
        "skills": ["system_design.md", "presentation_design.md"],
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
]


def _seed_default_agents():
    """Create the five default Mind Castle agents if none exist yet, or backfill new fields."""
    from app.services.agent_service import create_agent, list_agents, backfill_agent_fields

    existing = list_agents()
    if existing:
        # Backfill specialty/skills for existing agents that lack them
        fields_map = {
            d["name"]: {"specialty": d.get("specialty", ""), "skills": d.get("skills", [])}
            for d in DEFAULT_AGENTS
        }
        backfill_agent_fields(fields_map)
        return

    for agent_def in DEFAULT_AGENTS:
        create_agent(
            name=agent_def["name"],
            role=agent_def["role"],
            color=agent_def["color"],
            system_prompt=agent_def["system_prompt"],
            specialty=agent_def.get("specialty", ""),
            skills=agent_def.get("skills", []),
        )


@app.on_event("startup")
async def startup():
    settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    settings.agents_dir.mkdir(parents=True, exist_ok=True)
    settings.templates_dir.mkdir(parents=True, exist_ok=True)
    (settings.knowledge_dir / "insights").mkdir(parents=True, exist_ok=True)
    (settings.knowledge_dir / "skills").mkdir(parents=True, exist_ok=True)
    (settings.logs_dir / "errors").mkdir(parents=True, exist_ok=True)

    # Seed default Mind Castle agents (only if none exist yet)
    _seed_default_agents()

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
