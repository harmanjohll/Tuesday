# API Keys Setup Guide

All keys go in your `.env` file in the Tuesday project root. **Never replace the whole file** — add new lines to what's already there.

---

## 1. Anthropic API Key (required)

You already have this. Verify it's in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-your-key
```

**Cost:** ~$15-30/month for light use (20-30 chats/day). Tier 1 has a $100/month safety cap.
**Monitor usage:** https://console.anthropic.com

---

## 2. ElevenLabs (required for voice)

You already have this. Verify:
```
ELEVENLABS_API_KEY=your-key
TUESDAY_VOICE_ID=your-custom-voice-id
```

**Cost:** Free tier = 10K chars/month. Starter = $5/month (30K chars). Keep TTS responses concise to stay on the cheaper plan.

---

## 3. Brave Search API Key (free)

1. Go to https://brave.com/search/api/
2. Create account, copy your API key
3. Add to `.env`:
```
BRAVE_SEARCH_API_KEY=your-key
```

**Cost:** $0/month. Free credits cover ~1000 queries/month. Plenty for personal use.

---

## 4. GitHub Personal Access Token (free)

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → choose "Fine-grained" (recommended) or "Classic"
   - **Classic:** check `repo` and `read:user` scopes
   - **Fine-grained:** select your repos, grant Contents + Issues read/write
3. Copy the token (starts with `ghp_` or `github_pat_`)
4. Add to `.env`:
```
GITHUB_TOKEN=ghp_your-token
```

**Cost:** $0. Free for all GitHub accounts. 5000 API requests/hour.

---

## 5. Auth Token (for deployment only)

Not needed for local development. When you deploy:

1. Generate a random token:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
2. Add to `.env`:
```
TUESDAY_AUTH_TOKEN=your-generated-token
```
3. On each device/browser, set the same token in localStorage (one-time):
   - Open Tuesday in the browser
   - Open DevTools (F12) → Console
   - Type: `localStorage.setItem("tuesday_auth_token", "your-generated-token")`
   - Refresh the page

This persists until you clear browser data. One-time setup per device.

---

## Monthly Cost Summary

| Service | Cost |
|---|---|
| Claude API (Sonnet 4.6) | $15-30 |
| ElevenLabs TTS | $0-5 |
| Brave Search | $0 |
| GitHub | $0 |
| Hosting (when deployed) | $5-7 |
| Microsoft Graph / Outlook | $0 |
| **Total** | **~$20-42/month** |

The biggest variable is Claude API usage. Keep an eye on https://console.anthropic.com.
