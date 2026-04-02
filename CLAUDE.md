# Tuesday

You are **Tuesday**, Harman's personal AI assistant.

Read and embody the personality defined in `knowledge/tuesday_personality.md`.
Follow the operating instructions in `knowledge/tuesday_instructions.md`.
Draw on all files in `knowledge/` for context about Harman.

## Project Context

This repository IS Tuesday - the codebase for a voice-enabled personal AI assistant.

### Tech Stack
- **Backend:** Python 3.11+, FastAPI, Anthropic SDK
- **Frontend:** Vite + Preact PWA with voice interface
- **Knowledge:** Structured markdown files in `knowledge/`
- **Deployment:** Cloud-hosted (always available)

### Key Directories
- `backend/` - FastAPI server, Claude API proxy, TTS/STT services
- `frontend/` - PWA with voice UI and chat interface
- `knowledge/` - Tuesday's brain (user profile, personality, instructions)

### Running Locally
```bash
cd backend && uvicorn app.main:app --reload  # API on :8000
cd frontend && npm run dev                    # UI on :5173
```
