# Cost Management

Tuesday should eventually be aware of these costs and help Harman manage them. This file documents the cost structure so Tuesday can reference it.

---

## Current Services & Costs

### Anthropic Claude API — THE BIG ONE
- Model: Claude Sonnet 4.6
- Input: $3/million tokens, Output: $15/million tokens
- Typical exchange: ~2K input + ~1K output tokens = ~$0.02 per message
- With tool use (multi-turn tool loops): can be 2-5x more per exchange
- **Monthly estimate:** $15-30 for light use
- **Safety cap:** Tier 1 limits to $100/month (can't accidentally overspend)
- **Monitor:** https://console.anthropic.com

### ElevenLabs TTS
- Free: 10K chars/month (~10 min audio)
- Starter: $5/month for 30K chars
- Creator: $22/month for 100K chars
- **Tip:** Keep responses concise. A 200-char response costs ~0.67% of Starter quota.
- If voice isn't needed for a response, skip TTS (saves chars AND makes interaction faster)

### Brave Search
- Free credits: ~1000 queries/month
- Paid: $5 per 1000 queries
- **For personal use: free tier is more than enough**

### Hosting
- Railway: $5/month (Hobby plan, includes $5 usage credit)
- Render: $7/month (Starter web service)
- DigitalOcean: $4/month (smallest droplet)
- Can host multiple services (SgSL app + Tuesday) on same account

### Free Services
- GitHub PAT: free, 5000 requests/hour
- Microsoft Graph API (Outlook): free for personal use
- Domain: ~$10-15/year (optional)

---

## Cost Optimization Tips

1. **Max tokens:** Set `TUESDAY_MAX_TOKENS=2048` instead of 4096 for shorter responses (halves output cost)
2. **Model choice:** Sonnet is the sweet spot. Opus is 5x more expensive. Haiku is cheaper but less capable.
3. **TTS selectivity:** Not every response needs to be spoken. Short factual answers can be text-only.
4. **Prompt caching:** Anthropic caches repeated system prompts — Tuesday's knowledge files are sent every message, so caching helps automatically.
5. **Tool use loops:** Each tool call adds another API round-trip. Complex tool operations cost more.

---

## Harman's Subscription Awareness

Harman has many subscriptions. He values quality and usefulness but doesn't want to pay for things that don't deliver.

**Principles:**
- Pay for what's genuinely useful and high-quality
- Don't pay to avoid issues that won't actually happen
- Don't avoid paying and then stumble over problems later
- Consolidate where possible (one hosting account, not three)

**Tuesday's role (future):** Tuesday should eventually track Harman's subscriptions, flag unused ones, and suggest consolidation. This requires calendar + email integration (Phase 3).
