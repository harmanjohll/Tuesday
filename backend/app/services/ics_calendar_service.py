"""ICS calendar reader — fetches published Outlook calendar via ICS URL.

No OAuth needed. Works with any published ICS feed.
Read-only: for writing events, use Google Calendar.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, date

import httpx
from icalendar import Calendar

from app.config import settings

logger = logging.getLogger("tuesday.ics_calendar")

TIMEOUT = 20.0
SGT = timezone(timedelta(hours=8))


async def read_work_calendar(inp: dict) -> str:
    """Fetch and parse events from the published ICS calendar."""
    ics_url = settings.outlook_ics_url
    if not ics_url:
        return "Work calendar ICS URL not configured. Set OUTLOOK_ICS_URL in the .env file."

    days = inp.get("days", 7)
    max_results = min(inp.get("max_results", 20), 50)

    # Fetch ICS feed
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(ics_url)
        if resp.status_code != 200:
            return f"Could not fetch work calendar: HTTP {resp.status_code}"
    except Exception as e:
        return f"Could not fetch work calendar: {e}"

    # Parse ICS
    try:
        cal = Calendar.from_ical(resp.text)
    except Exception as e:
        return f"Could not parse calendar data: {e}"

    now = datetime.now(SGT)
    cutoff = now + timedelta(days=days)
    today = now.date()

    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("dtstart")
        if not dtstart:
            continue
        dt = dtstart.dt

        # Handle all-day events (date vs datetime)
        if isinstance(dt, date) and not isinstance(dt, datetime):
            event_date = dt
            if event_date < today or event_date > cutoff.date():
                continue
            time_str = f"{event_date.strftime('%A %B %d')} (all day)"
        else:
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=SGT)
            else:
                dt = dt.astimezone(SGT)

            if dt < now or dt > cutoff:
                continue
            time_str = dt.strftime("%A %B %d, %I:%M %p")

        summary = str(component.get("summary", "Untitled"))
        location = str(component.get("location", ""))
        loc_str = f" at {location}" if location else ""

        events.append((dt if isinstance(dt, datetime) else datetime.combine(event_date, datetime.min.time()),
                       f"- {time_str}: {summary}{loc_str}"))

    if not events:
        return f"No work calendar events in the next {days} days."

    # Sort by date and limit
    events.sort(key=lambda x: x[0])
    events = events[:max_results]

    lines = [f"Work calendar — next {days} days ({len(events)} events):"]
    lines.extend(e[1] for e in events)
    return "\n".join(lines)
