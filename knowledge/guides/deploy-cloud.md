# Deployment Guide

Tuesday runs as a single Docker container: Python backend serves both the API and the built frontend.

---

## Prerequisites

- All API keys in `.env` (see `setup-api-keys.md`)
- Docker installed (or use a PaaS that handles it)
- Auth token set: `TUESDAY_AUTH_TOKEN=something-random`

---

## Option A: Railway (Recommended — $5/month)

Easiest. Connect your GitHub repo, it deploys automatically.

1. Go to https://railway.app and sign up (GitHub login works)
2. Click "New Project" → "Deploy from GitHub Repo"
3. Select `harmanjohll/Tuesday`
4. Go to your service → Settings → Variables
5. Add all your `.env` variables (one by one, or bulk paste)
6. Railway auto-detects the Dockerfile and deploys
7. Go to Settings → Networking → "Generate Domain"
8. Your Tuesday is live at `https://tuesday-something.up.railway.app`

**To update:** Just push to GitHub. Railway redeploys automatically.

---

## Option B: Render ($7/month)

You already have a Render account.

1. Go to https://dashboard.render.com → "New" → "Web Service"
2. Connect your `harmanjohll/Tuesday` repo
3. Settings:
   - **Environment:** Docker
   - **Plan:** Starter ($7/month)
4. Add environment variables (same as `.env`)
5. Click "Create Web Service"
6. Render builds and deploys. Gives you a `.onrender.com` URL.

---

## Option C: DigitalOcean VPS ($4/month)

Most control. More manual setup.

1. Create a $4/month droplet (1 vCPU, 512MB RAM, Ubuntu 24.04)
2. SSH in: `ssh root@your-ip`
3. Install Docker:
```bash
curl -fsSL https://get.docker.com | sh
```
4. Clone and deploy:
```bash
git clone https://github.com/harmanjohll/Tuesday.git
cd Tuesday
nano .env    # paste your environment variables
docker compose up -d --build
```
5. Tuesday is at `http://your-ip:8000`

**To update:**
```bash
cd Tuesday && git pull && docker compose up -d --build
```

---

## After Deployment

### Access from phone
1. Open the deployment URL in Chrome on your phone
2. Chrome prompts "Add to Home Screen" — tap "Add"
3. Tuesday appears as an app icon
4. First time: set the auth token in DevTools console:
   ```javascript
   localStorage.setItem("tuesday_auth_token", "your-token")
   ```
5. Refresh. You're in.

### Custom domain (optional)
- Buy a domain (~$10-15/year)
- Point it to your deployment
- Railway/Render handle HTTPS automatically
- For VPS: use Caddy (`caddy reverse-proxy --from tuesday.yourdomain.com --to localhost:8000`)

---

## Troubleshooting

**401 Unauthorized:** Auth token mismatch. Check that `TUESDAY_AUTH_TOKEN` in `.env` matches what's in `localStorage`.

**No voice:** `ELEVENLABS_API_KEY` missing or expired.

**No search results:** `BRAVE_SEARCH_API_KEY` missing. Check https://brave.com/search/api/.

**GitHub tools not working:** `GITHUB_TOKEN` missing or expired. Regenerate at https://github.com/settings/tokens.

**Container won't start:** Check `docker compose logs` for error messages. Usually a missing `ANTHROPIC_API_KEY`.
