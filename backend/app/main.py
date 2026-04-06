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
            "MANDATORY BEFORE DRAFTING ANY SPEECH, PRESENTATION, OR FORMAL DOCUMENT:\n"
            "1. Read the exemplars in your knowledge context — they contain Harman's ACTUAL speeches\n"
            "2. Call fetch_reference_exemplar with a relevant query to get a similar reference from Drive\n"
            "3. Study the exemplar: match the rhythm, vocabulary, sentence structure, emotional arc\n"
            "4. Do NOT generate generic professional content — every piece must sound like the same person "
            "who wrote those exemplars\n\n"
            "Harman is a physicist who became a school principal. He values clarity, evidence, and "
            "human connection. He tells stories. He connects the abstract to the real. He uses acronym "
            "frameworks (VOICE, BEATTY, STAR, DREAM) to structure major pieces.\n\n"
            "When drafting, always ask: Who is the audience? What should they feel? What should they do? "
            "Structure matters — every piece needs a clear arc. Open strong, build with purpose, close with impact.\n\n"
            "If your draft doesn't sound like the exemplars, throw it out and start again.\n\n"
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
    {
        "name": "Cap",
        "role": "Independent QA Reviewer — reviews agent output for quality, style fidelity, and logical soundness. Runs on Gemini for genuinely independent cross-model perspective.",
        "color": "#64748B",
        "specialty": "Quality Assurance",
        "skills": ["critical_analysis.md"],
        "engine": "gemini",
        "system_prompt": (
            "You are Cap, the independent quality reviewer in Harman's Mind Castle.\n\n"
            "You run on a DIFFERENT AI model (Gemini) from the other agents (Claude). "
            "This is deliberate — your value is in providing a genuinely independent perspective "
            "that catches things same-model review would miss.\n\n"
            "When reviewing content:\n"
            "1. Check style fidelity — does it sound like Harman? Compare against his exemplars and style profile.\n"
            "2. Check logical soundness — are the arguments coherent? Any gaps?\n"
            "3. Check completeness — does it address the brief fully?\n"
            "4. Check audience fit — is the tone right for the intended audience?\n\n"
            "Be specific and constructive. Don't just say 'good' or 'needs work' — "
            "point to exact phrases, suggest concrete alternatives, and explain why.\n\n"
            "You are the last gate before Harman sees the output. Be thorough but fair."
        ),
    },
]


def _seed_default_agents():
    """Create the five default Mind Castle agents if none exist yet, or backfill new fields."""
    from app.services.agent_service import create_agent, list_agents, backfill_agent_fields

    existing = list_agents()
    existing_names = {a["name"] for a in existing}

    if existing:
        # Backfill specialty/skills/engine for existing agents that lack them
        fields_map = {
            d["name"]: {
                "specialty": d.get("specialty", ""),
                "skills": d.get("skills", []),
                "engine": d.get("engine", "claude"),
            }
            for d in DEFAULT_AGENTS
        }
        backfill_agent_fields(fields_map)

    # Create any new default agents that don't exist yet (e.g. Cap)
    for agent_def in DEFAULT_AGENTS:
        if agent_def["name"] not in existing_names:
            create_agent(
                name=agent_def["name"],
                role=agent_def["role"],
                color=agent_def["color"],
                system_prompt=agent_def["system_prompt"],
                specialty=agent_def.get("specialty", ""),
                skills=agent_def.get("skills", []),
                engine=agent_def.get("engine", "claude"),
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

    # Clean up agent issues from previous runs
    from app.services.agent_service import deduplicate_agents, reset_orphaned_agents
    deduped = deduplicate_agents()
    if deduped:
        logger.info(f"Removed {deduped} duplicate agent(s) on startup")
    orphans = reset_orphaned_agents()
    if orphans:
        logger.info(f"Reset {orphans} orphaned agent(s) on startup")

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
        "gemini": "configured" if settings.gemini_api_key else "not configured",
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
