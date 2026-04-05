# Accounts & Costs

All active services for Tuesday. Reference this when Harman asks about costs or when advising on budget.

---

## Active Accounts

| Service | What it does | Cost | Dashboard | How to cancel |
|---------|-------------|------|-----------|---------------|
| **Anthropic** | Claude API (Tuesday's brain) | ~$15-30/month | console.anthropic.com | Settings → Close account |
| **DigitalOcean** | Droplet server (Tuesday's home) | $6/month | cloud.digitalocean.com | Droplet → Destroy |
| **ElevenLabs** | Voice/TTS | Free tier or $5/month | elevenlabs.io | Subscription → Cancel |
| **Brave Search** | Web search | Free (1000 queries/month) | brave.com/search/api | No cost — just delete key |
| **Namecheap** | Domain (tuesdayai.co) | ~$10/year | namecheap.com | Turn off auto-renew |
| **Google Cloud** | Gmail OAuth | Free | console.cloud.google.com | Delete project "Tuesday" |
| **GitHub** | Code hosting + PAT | Free | github.com | Developer Settings → delete token |

---

## Monthly Cost Summary

- **Minimum (text only):** ~$21/month ($15 Anthropic + $6 DigitalOcean)
- **Typical (with voice):** ~$26/month (+ $5 ElevenLabs)
- **Maximum (heavy use):** ~$50/month (higher API usage)
- **Annual fixed:** ~$10 domain

---

## Future Feature Costs

| Feature | Additional cost | Notes |
|---------|----------------|-------|
| Morning briefing | $0 | Uses existing Claude API |
| Document analysis | $0 | Uses existing Claude API (vision) |
| Code agent (GitHub write) | $0 | Uses existing GitHub token |
| WhatsApp bridge | $0-5/month | Twilio or self-hosted |
| Google Drive/Docs | $0 | Free API, same OAuth pattern |

---

## To Shut Everything Down

Priority order (stops charges fastest):
1. **DigitalOcean:** cloud.digitalocean.com → Droplets → `tuesday` → Destroy
2. **Anthropic:** console.anthropic.com → delete API key
3. **ElevenLabs:** elevenlabs.io → Cancel subscription (if paid)
4. **Namecheap:** Turn off auto-renew on tuesdayai.co
5. **Google Cloud:** console.cloud.google.com → Shut down project
6. **GitHub:** Revoke PAT (no cost, but good practice)
7. **Brave:** Delete API key (no cost)

Steps 1 and 2 stop all meaningful charges immediately.
