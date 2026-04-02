# Tuesday

A personal AI assistant that runs as a layer on top of Claude. Voice-enabled, always-on, built to know its user.

## Architecture

```
Phone/Laptop Browser (PWA)
        |
   Tuesday Backend (FastAPI + Claude API)
        |
   Knowledge Layer (structured markdown files)
```

## Structure

- `backend/` - FastAPI server, Claude API proxy, TTS/STT services
- `frontend/` - PWA with voice interface, chat UI
- `knowledge/` - Tuesday's brain: user profile, personality, instructions

## Quick Start

```bash
# Backend
cd backend
pip install -e .
cp .env.example .env  # Add your API keys
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Requirements

- Python 3.11+
- Node 18+
- Anthropic API key
- TTS/STT API key (ElevenLabs or OpenAI)
