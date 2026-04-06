"""Google Calendar API client.

Uses the same OAuth tokens as Gmail (expanded scopes).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger("tuesday.gcalendar")

CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
TIMEOUT = 15.0
SGT = timezone(timedelta(hours=8))


async def _get_token() -> str | None:
    from app.routers.auth_gmail import load_tokens, refresh_access_token
    tokens = load_tokens()
    if not tokens:
        return None
    # Always try refresh first — ensures we have latest scopes
    refreshed = await refresh_access_token()
    return refreshed or tokens.get("access_token")


def _check() -> str | None:
    from app.routers.auth_gmail import load_tokens
    from app.config import settings
    if not settings.google_client_id:
        return "Google app not configured."
    if not load_tokens():
        return "Google not connected. Visit /auth/gmail to log in (covers Calendar too)."
    return None


async def _cal_request(method: str, path: str, **kwargs) -> dict | str:
    from app.routers.auth_gmail import refresh_access_token
    token = await _get_token()
    if not token:
        return "No valid Google token."

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.request(method, f"{CALENDAR_BASE}{path}", headers=headers, **kwargs)

    if resp.status_code == 401:
        new_token = await refresh_access_token()
        if not new_token:
            return "Google auth expired. Re-login at /auth/gmail."
        headers["Authorization"] = f"Bearer {new_token}"
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.request(method, f"{CALENDAR_BASE}{path}", headers=headers, **kwargs)

    if resp.status_code not in (200, 201):
        return f"Calendar API error: {resp.status_code} {resp.text[:200]}"
    return resp.json()


async def list_events(inp: dict) -> str:
    if err := _check():
        return err

    days = inp.get("days", 7)
    max_results = min(inp.get("max_results", 15), 25)

    now = datetime.now(SGT)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    data = await _cal_request("GET", "/calendars/primary/events", params={
        "timeMin": time_min,
        "timeMax": time_max,
        "maxResults": max_results,
        "singleEvents": "true",
        "orderBy": "startTime",
    })

    if isinstance(data, str):
        if "401" in data or "auth" in data.lower() or "expired" in data.lower():
            return f"{data}\n\nTry re-authenticating at /auth/gmail to refresh calendar permissions."
        return data

    events = data.get("items", [])
    if not events:
        return f"No events in the next {days} days."

    lines = [f"Events for the next {days} days ({len(events)}):"]
    for ev in events:
        start = ev.get("start", {})
        dt_str = start.get("dateTime", start.get("date", ""))
        try:
            dt = datetime.fromisoformat(dt_str)
            time_str = dt.strftime("%A %B %d, %I:%M %p")
        except (ValueError, TypeError):
            time_str = dt_str

        summary = ev.get("summary", "Untitled")
        location = ev.get("location", "")
        loc_str = f" at {location}" if location else ""
        lines.append(f"- {time_str}: {summary}{loc_str}")

    return "\n".join(lines)


async def create_event(inp: dict) -> str:
    if err := _check():
        return err

    body = {
        "summary": inp["summary"],
        "start": {"dateTime": inp["start"], "timeZone": "Asia/Singapore"},
        "end": {"dateTime": inp["end"], "timeZone": "Asia/Singapore"},
    }
    if inp.get("location"):
        body["location"] = inp["location"]
    if inp.get("description"):
        body["description"] = inp["description"]

    data = await _cal_request("POST", "/calendars/primary/events", json=body)
    if isinstance(data, str):
        return data

    return f"Created event: {data.get('summary', 'Untitled')} on {inp['start'][:10]}"


async def delete_event(inp: dict) -> str:
    if err := _check():
        return err

    event_id = inp["event_id"]
    token = await _get_token()
    if not token:
        return "No valid Google token."

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.delete(
            f"{CALENDAR_BASE}/calendars/primary/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    if resp.status_code == 204:
        return "Event deleted."
    return f"Error deleting event: {resp.status_code}"
