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

## Option C: DigitalOcean Droplet (Recommended — $6/month)

The best option for Tuesday because your data (conversations, knowledge, tokens) stays on disk. Step-by-step below.

### Step 1: Create a Droplet

1. Log in to https://cloud.digitalocean.com
2. Click the green **"Create"** button (top right) → **"Droplets"**
3. Choose these settings:
   - **Region:** Singapore (SGP1) — closest to you
   - **Image:** Ubuntu 24.04 (LTS)
   - **Size:** Basic → Regular → **$6/month** (1 vCPU, 1 GB RAM, 25 GB disk)
   - **Authentication:** Choose **Password** (simpler) — set a strong root password and save it somewhere safe
   - **Hostname:** `tuesday` (or whatever you like)
4. Click **"Create Droplet"**
5. Wait ~60 seconds. You'll see an **IP address** (like `165.22.xxx.xxx`). Copy it.

### Step 2: Connect to your Droplet

Open Terminal (Mac) or PowerShell (Windows) and type:

```bash
ssh root@YOUR_IP_ADDRESS
```

It will ask for the password you set in Step 1. Type it (nothing shows while typing — that's normal). Press Enter.

You're now inside your server.

### Step 3: Install Docker

Copy and paste these two lines (one at a time):

```bash
apt update && apt upgrade -y
```

```bash
curl -fsSL https://get.docker.com | sh
```

Wait for each to finish. Docker is now installed.

### Step 4: Get Tuesday's code

```bash
git clone https://github.com/harmanjohll/Tuesday.git
cd Tuesday
```

### Step 5: Set up your environment variables

```bash
cp .env.example .env
nano .env
```

This opens a text editor. Fill in your API keys:

- `ANTHROPIC_API_KEY=sk-ant-...` — **required** (from Anthropic console)
- `ELEVENLABS_API_KEY=...` — for voice (from ElevenLabs dashboard)
- `BRAVE_SEARCH_API_KEY=...` — for web search (from Brave)
- `GITHUB_TOKEN=...` — for GitHub tools (from GitHub settings)
- `TUESDAY_AUTH_TOKEN=...` — **important for security!** Generate one:
  ```
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
  Copy the output and paste it as the value.
- `TUESDAY_ENV=production`

To save in nano: press `Ctrl+O`, then `Enter`, then `Ctrl+X` to exit.

### Step 6: Deploy

```bash
docker compose up -d --build
```

This builds the container and starts Tuesday. First time takes 2-3 minutes.

### Step 7: Check it's running

```bash
docker compose logs -f
```

You should see: `Uvicorn running on http://0.0.0.0:8000`

Press `Ctrl+C` to stop watching logs (Tuesday keeps running).

### Step 8: Open Tuesday in your browser

Go to: `http://YOUR_IP_ADDRESS:8000`

You should see the Tuesday interface!

### Step 9: Set your auth token in the browser

Open your browser's developer console:
- **Chrome:** Press `F12` → click "Console" tab
- **Safari:** Enable Developer menu in preferences, then `Cmd+Option+C`

Paste this (replace with your actual token from Step 5):

```javascript
localStorage.setItem("tuesday_auth_token", "your-TUESDAY_AUTH_TOKEN-value-here")
```

Press Enter, then refresh the page. You're in!

### Step 10: Access from your phone

1. Open `http://YOUR_IP_ADDRESS:8000` in **Chrome** on your phone
2. Tap the **three dots menu** (top right) → **"Add to Home Screen"**
3. Tap **"Add"** — Tuesday appears as an app icon on your home screen
4. Open it, set the auth token the same way (Chrome menu → "Developer tools" on Android)

### Updating Tuesday later

When there's a new version:

```bash
ssh root@YOUR_IP_ADDRESS
cd Tuesday
git pull
docker compose up -d --build
```

Done in under a minute.

### Optional: Custom domain + HTTPS

If you want `https://tuesday.yourdomain.com` instead of an IP:

1. Buy a domain (Namecheap, Cloudflare — ~$10-15/year)
2. In your domain's DNS settings, add an **A record** pointing to your Droplet's IP
3. SSH into your Droplet and install Caddy (auto-HTTPS):
   ```bash
   apt install -y debian-keyring debian-archive-keyring apt-transport-https
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
   curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
   apt update && apt install caddy
   ```
4. Create a Caddyfile:
   ```bash
   nano /etc/caddy/Caddyfile
   ```
   Paste:
   ```
   tuesday.yourdomain.com {
       reverse_proxy localhost:8000
   }
   ```
   Save (`Ctrl+O`, Enter, `Ctrl+X`).
5. Restart Caddy:
   ```bash
   systemctl restart caddy
   ```
6. Caddy automatically gets an HTTPS certificate. Your Tuesday is now at `https://tuesday.yourdomain.com`.
7. Update `MICROSOFT_REDIRECT_URI` and `GOOGLE_REDIRECT_URI` in `.env` to use your domain, then rebuild:
   ```bash
   docker compose up -d --build
   ```

---

## After Deployment

### Connecting Gmail (personal email)
1. Set up Google OAuth (see `setup-api-keys.md`)
2. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env`
3. Rebuild: `docker compose up -d --build`
4. Visit `http://YOUR_IP:8000/auth/gmail` and log in with your Google account
5. Ask Tuesday: "Any unread personal emails?"

### Connecting Outlook (work calendar — when IT approves)
1. Register app in Azure AD (needs IT help for school M365)
2. Add `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET` to `.env`
3. Rebuild: `docker compose up -d --build`
4. Visit `http://YOUR_IP:8000/auth/outlook?account=work` and log in
5. Ask Tuesday: "What's my day look like?"

---

## Troubleshooting

**Can't SSH in:** Double-check the IP address and password. DigitalOcean also lets you open a console from their web dashboard (Droplet → "Access" → "Launch Droplet Console").

**401 Unauthorized:** Auth token mismatch. The token in your browser's `localStorage` must exactly match `TUESDAY_AUTH_TOKEN` in `.env`.

**No voice:** `ELEVENLABS_API_KEY` missing or expired. Check your ElevenLabs dashboard.

**No search results:** `BRAVE_SEARCH_API_KEY` missing. Get a free key at https://brave.com/search/api/.

**GitHub tools not working:** `GITHUB_TOKEN` missing or expired. Regenerate at https://github.com/settings/tokens.

**Container won't start:** Run `docker compose logs` and look for error messages. Most common: missing `ANTHROPIC_API_KEY`.

**Port 8000 not accessible:** DigitalOcean firewalls may block it. Go to your Droplet → "Networking" → "Firewall" and add an inbound rule for TCP port 8000.

**Out of disk space:** Run `docker system prune -f` to clean up old images.
