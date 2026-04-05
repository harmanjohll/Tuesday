# Tuesday: The Journey

> How a school principal and an AI built a personal intelligence system from scratch.

This document traces every step of building **Tuesday** -- a voice-enabled personal AI assistant with quantum-inspired visuals, deep integrations, and a parallel agent system called the Mind Castle. It's written so you can learn from it, replicate it, or just appreciate the ride.

**Built by:** Harman (human) + Claude (AI)
**Timeline:** April 2026
**Stack:** Python/FastAPI + Preact PWA + Claude API

---

## Table of Contents

1. [The Vision](#the-vision)
2. [Build Timeline](#build-timeline)
3. [What Tuesday Can Do Today](#what-tuesday-can-do-today)
4. [Architecture](#architecture)
5. [How to Build This Yourself](#how-to-build-this-yourself)
6. [Learning References](#learning-references)

---

## The Vision

Tuesday is Harman's personal AI -- not a chatbot, but a second brain. It knows who he is, what he values, how he thinks, and what he's working on. It speaks with a distinct personality. It can read his email, check his calendar, create presentations, run code, search the web, and delegate tasks to specialist agents.

The name "Tuesday" comes from the AI assistant in Marvel's Iron Man universe. The visual identity -- a pulsing quantum nebula -- represents the idea that infinity exists within the infinitesimal.

---

## Build Timeline

### Phase 0: Foundation (Commits 1-8)

**What was built:** The skeleton -- a FastAPI backend proxying Claude API, a Preact frontend with a chat interface, and the first version of the quantum particle visualization.

| Step | What | Why | Key Files |
|------|------|-----|-----------|
| 1 | Initial commit | Repo scaffold | `README.md` |
| 2 | Core app: chat + voice + PWA | Get a working AI assistant in the browser | `backend/app/main.py`, `frontend/src/app.jsx` |
| 3 | Quantum particle visuals | Give Tuesday a living visual identity | `frontend/src/particles.jsx` |
| 4 | TTS via ElevenLabs | Tuesday should speak, not just type | `backend/app/services/tts_service.py` |
| 5 | Fix TTS blocking | Audio was freezing the app -- needed async streaming | `tts_service.py` |
| 6 | Always-on mic | Voice-first interface using Web Speech API | `frontend/src/voice.jsx` |
| 7 | Fix autoplay | Chrome blocks audio autoplay -- added click-to-unlock | `app.jsx` |
| 8 | Layout: SAR full-screen, chat overlay | Chat window over the nebula, not beside it | `style.css` |

**Concepts learned:**
- **Server-Sent Events (SSE):** How to stream Claude's response token-by-token to the frontend
- **Web Speech API:** Browser-native speech recognition (Chrome only)
- **ElevenLabs API:** Text-to-speech with custom voice cloning
- **Preact:** Lightweight React alternative (~3KB) perfect for PWAs

### Phase 1: Memory + Tools (Commits 9-15)

**What was built:** Tuesday can remember things, use tools, search the web, connect to GitHub, and protect itself with authentication.

| Step | What | Why | Key Files |
|------|------|-----|-----------|
| 9 | Knowledge files | Give Tuesday a persistent understanding of Harman | `knowledge/*.md` |
| 10 | Deep profiling | Extended conversations to build rich personality profiles | `knowledge/disposition.md`, `expertise.md`, `principles.md` |
| 11 | Session memory + tool use | Remember conversations, update own knowledge | `backend/app/services/session_service.py`, `tools/executor.py` |
| 12 | Web search (Brave API) | Look up facts Tuesday doesn't know | `tools/executor.py` |
| 13 | GitHub integration | Create repos, search code, manage files, create PRs | `tools/github_tools.py` |
| 14 | Auth middleware | Protect the API with bearer tokens | `middleware/auth.py` |
| 15 | Docker deployment | Package everything for cloud hosting | `Dockerfile`, `docker-compose.yml` |

**Concepts learned:**
- **Claude Tool Use:** Defining tools as JSON schemas, handling `tool_use` stop reasons, looping until done
- **System Prompt Engineering:** Loading structured markdown files as Claude's system prompt
- **Session Consolidation:** Auto-summarizing old messages to keep context manageable
- **Bearer Token Auth:** Simple but effective API protection

### Phase 2: Email + Calendar (Commits 16-22)

**What was built:** Tuesday reads email, manages calendars, and handles OAuth flows for Google and Microsoft.

| Step | What | Why | Key Files |
|------|------|-----|-----------|
| 16 | Outlook integration | Read work calendar and email via Microsoft Graph | `services/outlook_service.py`, `routers/auth_outlook.py` |
| 17 | Gmail integration | Read personal email, send messages | `services/gmail_service.py`, `routers/auth_gmail.py` |
| 18 | Gmail write tools | Mark read, archive, trash | `tools/executor.py` |
| 19 | Google Calendar | List, create, delete events | `services/gcalendar_service.py` |
| 20 | Google Drive | List, search, read files | `services/gdrive_service.py` |
| 21 | ICS calendar reader | Read work calendar via published feed (no OAuth needed) | `services/ics_calendar_service.py` |
| 22 | Multi-model routing | Use Haiku for simple queries, Sonnet default, Opus for complex reasoning | `services/claude_service.py` |

**Concepts learned:**
- **OAuth 2.0 Flow:** Authorization code grant, token refresh, scope management
- **Microsoft Graph API:** Calendar views, mail folders, multi-account support
- **Google APIs:** Gmail, Calendar, Drive -- all sharing one OAuth token
- **Model Routing:** Choosing the right Claude model based on query complexity

### Phase 3: Content Creation + Data (Commits 23-28)

**What was built:** Tuesday generates documents, runs code, queries statistics, manages decisions and reminders, and syncs its brain to GitHub.

| Step | What | Why | Key Files |
|------|------|-----|-----------|
| 23 | Brain repo | Sync knowledge files to `harmanjohll/brain` on GitHub | `tools/brain_tools.py` |
| 24 | Content creation | Generate PowerPoint, Word, and PDF files | `services/document_generator.py` |
| 25 | Reminders | Set, list, dismiss reminders with repeat support | `tools/executor.py` |
| 26 | Python sandbox | Execute code safely (numpy, matplotlib, pandas) | `services/sandbox_service.py` |
| 27 | Statistics APIs | Query data.gov.sg, World Bank, WHO | `services/statistics_service.py` |
| 28 | Morning briefing | Auto-generated at 6am SGT: emails + calendar + reminders | `services/briefing_service.py` |

**Concepts learned:**
- **python-pptx / python-docx / reportlab:** Programmatic document generation
- **Sandboxed Execution:** Running untrusted code safely with subprocess restrictions
- **APScheduler:** Background job scheduling in FastAPI
- **Time Capsules:** Using Git tags as temporal snapshots of knowledge

### Phase 4: Visual Identity (Commits 29-32)

**What was built:** The SAR (Sentience Art Representation) was redesigned multiple times to find the right visual soul.

| Step | What | Why | Key Files |
|------|------|-----|-----------|
| 29 | Nebula-inside-atom concept | Infinity within the infinitesimal | `particles.jsx` |
| 30 | Warm crimson palette | Shifted from blue/cool to warm/living | `particles.jsx` |
| 31 | Radiating pulse rings | Heartbeat rings that expand outward | `particles.jsx` |
| 32 | Remove black circle, soften core | More organic, less mechanical | `particles.jsx` |

**The visual metaphor:** Stars are electrons. The nebula is the electron cloud. Inside the atom's core: the cosmos itself. The heartbeat is a dual-peak waveform (like a real human heartbeat), driven by BPM that changes with Tuesday's state (idle: 54bpm, thinking: 78bpm).

### Phase 5: Mind Castle + Templates (Latest)

**What was built:** A parallel agent system with distinct visual identities, corporate template support, and knowledge reorganization.

| Step | What | Why | Key Files |
|------|------|-----|-----------|
| 33 | Agent data model | Named agents with roles, colors, sessions | `models/agent.py` |
| 34 | Agent service | Create, chat, assign tasks, background execution | `services/agent_service.py` |
| 35 | Agent REST API | Full CRUD + SSE chat streaming per agent | `routers/agents.py` |
| 36 | Tuesday agent tools | Tuesday can spawn agents and delegate | `tools/definitions.py`, `executor.py` |
| 37 | Template system | Upload and use corporate PPTX/DOCX templates | `services/template_service.py` |
| 38 | Mind Castle UI | Swipeable panel with agent orb grid | `frontend/src/mindcastle.jsx` |
| 39 | Agent orbs | Per-agent colored particle systems | `frontend/src/agent-orb.jsx` |
| 40 | Knowledge reorg | Monthly summaries, knowledge index | `knowledge/index.md`, `summaries/` |

**Concepts learned:**
- **Async Background Tasks:** `asyncio.create_task()` for fire-and-forget agent work
- **Touch Gesture Detection:** `touchstart`/`touchend` for swipe navigation
- **Canvas Per-Component:** Multiple independent canvas animations (performance-conscious)
- **File-Based Persistence:** JSON files as a lightweight alternative to databases

---

## What Tuesday Can Do Today

### Core
- Voice + text chat with Claude (streaming SSE)
- Always-on microphone with interrupt support
- Custom voice via ElevenLabs
- Living quantum nebula visualization that breathes with state

### Knowledge
- 9 structured knowledge files about Harman (identity, values, expertise, context)
- Session memory with auto-consolidation
- Decision journal with follow-up tracking
- Reminders with repeat scheduling
- Brain sync to GitHub (portable identity)

### Integrations
- **Email:** Gmail + Outlook (read, send, archive, trash)
- **Calendar:** Google Calendar + Outlook + ICS feeds (read, create, delete)
- **Google Drive:** List, search, read files
- **GitHub:** Repos, code search, issues, PRs, file management
- **Web Search:** Brave Search API

### Content Creation
- PowerPoint presentations (with corporate template support)
- Word documents (formal, casual, memo styles)
- PDF reports
- Python code execution with matplotlib plots
- Statistics from Singapore, World Bank, WHO

### Mind Castle (Agent System)
- Create named specialist agents with unique colored orbs
- Assign background tasks to agents
- Chat directly with any agent
- Tuesday can delegate work to agents
- Swipeable panel between Tuesday and Mind Castle

### Infrastructure
- Bearer token authentication
- Multi-model routing (Haiku/Sonnet/Opus)
- Morning briefing scheduler (6am SGT)
- Docker deployment
- PWA (installable on phone)

---

## Architecture

```
Browser (Preact PWA)
  |
  |-- SSE stream (/chat) -------> FastAPI Backend
  |-- Voice (/chat/speak) ------> TTS Service (ElevenLabs)
  |-- Agents (/agents) ---------> Agent Service
  |-- Files (/documents) -------> Document Generator
  |
  FastAPI Backend
    |-- Claude API (Anthropic SDK)
    |-- Tool Executor (40+ tools)
    |   |-- Knowledge tools (read/write markdown)
    |   |-- GitHub tools (via REST API)
    |   |-- Google tools (OAuth + REST)
    |   |-- Microsoft tools (OAuth + Graph API)
    |   |-- Agent tools (spawn, delegate, read)
    |   |-- Content tools (PPTX, DOCX, PDF)
    |   |-- Code sandbox (subprocess)
    |   |-- Web search (Brave API)
    |
    |-- Session Service (JSON files)
    |-- Knowledge Loader (markdown -> system prompt)
    |-- Scheduler (APScheduler, morning briefings)
```

### Key Directories
```
Tuesday/
  backend/
    app/
      main.py                 # FastAPI app entry point
      config.py               # Settings from .env
      middleware/auth.py       # Bearer token auth
      routers/                # API endpoints (chat, voice, agents, etc.)
      services/               # Integration services (15 modules)
      tools/                  # Tool definitions + executor
      models/                 # Data models (Agent)
    sessions/                 # Conversation history (JSON)
    agents/                   # Agent data (JSON per agent)
    templates/                # Uploaded PPTX/DOCX templates
    outputs/                  # Generated documents
  frontend/
    src/
      app.jsx                 # Main chat UI + panel system
      voice.jsx               # Web Speech API wrapper
      particles.jsx           # Tuesday's quantum nebula (SAR)
      agent-orb.jsx           # Per-agent colored particle orb
      mindcastle.jsx          # Mind Castle panel
      style.css               # Dark theme + Mind Castle styles
  knowledge/                  # Tuesday's brain (markdown files)
    tuesday_personality.md    # How Tuesday speaks
    tuesday_instructions.md   # Operating rules
    identity.md               # Who Harman is
    disposition.md            # How Harman thinks
    expertise.md              # What Harman knows
    preferences.md            # What Harman prefers
    principles.md             # What Harman believes
    context.md                # What's happening now
    decisions.md              # Decision journal
    reminders.md              # Active reminders
    summaries/                # Monthly session summaries
    index.md                  # Knowledge file index
```

---

## How to Build This Yourself

### Prerequisites
- Python 3.11+
- Node.js 20+
- API keys: Anthropic (Claude), ElevenLabs or OpenAI (TTS), optionally Brave Search

### Step 1: Backend Foundation
```bash
mkdir my-assistant && cd my-assistant
mkdir -p backend/app/{routers,services,tools,middleware} frontend/src knowledge
```

Create `backend/app/main.py` with FastAPI, a `/chat` SSE endpoint that proxies to Claude, and a `/chat/speak` endpoint for TTS. This is your minimum viable assistant.

**Key libraries:**
```
pip install fastapi uvicorn anthropic httpx sse-starlette python-dotenv
```

### Step 2: Frontend
```bash
cd frontend && npm init -y
npm install preact @preact/preset-vite vite
```

Build a simple chat UI in Preact. Add voice input with the Web Speech API. Add a canvas animation if you want visuals.

### Step 3: Knowledge System
Create markdown files in `knowledge/` describing:
- The assistant's personality (how it speaks)
- Operating instructions (what it should/shouldn't do)
- Information about you (identity, preferences, values)

Load these into the system prompt. This is what makes the assistant *yours*.

### Step 4: Tool Use
Define tools in Anthropic's JSON schema format. Start with basics:
- `update_knowledge` -- let the assistant update its own knowledge files
- `web_search` -- look things up
- `read_file` / `write_file` -- filesystem access

Implement a tool execution loop: send message -> check for tool_use -> execute tool -> feed result back -> repeat until done.

### Step 5: Integrations
Add OAuth flows for Google and Microsoft. Each integration follows the same pattern:
1. OAuth router (redirect to provider, handle callback, store tokens)
2. Service module (API calls with token refresh)
3. Tool definitions (so Claude knows about the capability)
4. Executor dispatch (route tool calls to service methods)

### Step 6: Deploy
Dockerize with a multi-stage build: Node builds the frontend, Python runs everything. Deploy to Railway, Fly.io, or any VPS with Docker.

### Step 7: Agent System (Advanced)
Add a parallel agent system where the main assistant can spawn specialist agents. Each agent needs:
- Its own data model (name, role, color, status, messages)
- A background task runner (asyncio)
- SSE streaming for real-time chat
- A frontend panel to visualize and interact with agents

---

## Learning References

### Core Technologies
| Topic | Resource | Used For |
|-------|----------|----------|
| **FastAPI** | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) | Backend framework |
| **Preact** | [preactjs.com](https://preactjs.com) | Lightweight frontend |
| **Vite** | [vitejs.dev](https://vitejs.dev) | Build tool |
| **Claude API** | [docs.anthropic.com](https://docs.anthropic.com) | AI backbone |

### AI & Voice
| Topic | Resource | Used For |
|-------|----------|----------|
| **Claude Tool Use** | [Anthropic docs: Tool Use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview) | Giving Claude abilities |
| **Streaming (SSE)** | [MDN: Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) | Real-time token display |
| **ElevenLabs API** | [elevenlabs.io/docs](https://elevenlabs.io/docs) | Custom voice TTS |
| **Web Speech API** | [MDN: SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition) | Browser voice input |

### Integrations
| Topic | Resource | Used For |
|-------|----------|----------|
| **Google OAuth** | [Google Identity: OAuth 2.0](https://developers.google.com/identity/protocols/oauth2) | Gmail, Calendar, Drive |
| **Microsoft Graph** | [learn.microsoft.com/graph](https://learn.microsoft.com/en-us/graph/overview) | Outlook calendar + email |
| **GitHub REST API** | [docs.github.com/rest](https://docs.github.com/en/rest) | Repo management |
| **Brave Search API** | [brave.com/search/api](https://brave.com/search/api/) | Web search |

### Document Generation
| Topic | Resource | Used For |
|-------|----------|----------|
| **python-pptx** | [python-pptx.readthedocs.io](https://python-pptx.readthedocs.io) | PowerPoint files |
| **python-docx** | [python-docx.readthedocs.io](https://python-docx.readthedocs.io) | Word documents |
| **ReportLab** | [reportlab.com/docs](https://www.reportlab.com/docs/reportlab-userguide.pdf) | PDF generation |

### Concepts
| Topic | Resource | Used For |
|-------|----------|----------|
| **PWA** | [web.dev/progressive-web-apps](https://web.dev/explore/progressive-web-apps) | Installable web app |
| **Canvas 2D API** | [MDN: Canvas API](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API) | Particle animations |
| **OAuth 2.0** | [oauth.net/2](https://oauth.net/2/) | Auth flows |
| **asyncio** | [Python docs: asyncio](https://docs.python.org/3/library/asyncio.html) | Background tasks |
| **Docker Multi-Stage** | [Docker docs: Multi-stage builds](https://docs.docker.com/build/building/multi-stage/) | Deployment |

---

## Stats

- **Total commits:** 45+
- **Backend:** ~4,500 lines Python across 25 files
- **Frontend:** ~1,700 lines JSX/CSS across 6 files
- **Knowledge:** ~500 lines markdown across 12 files
- **Tools:** 40+ tool definitions
- **Integrations:** 8 external services
- **Time:** Built iteratively across multiple sessions in April 2026

---

*Last updated: 2026-04-05*
