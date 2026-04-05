"""Microsoft Graph API client for Outlook calendar and email.

All methods return human-readable strings (not JSON) so Claude
can synthesize them into natural speech. Email content is never
persisted to disk — only held in memory for the active request.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

logger = logging.getLogger("tuesday.outlook")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TIMEOUT = 15.0
SGT = timezone(timedelta(hours=8))  # Singapore Time


async def _get_token(account: str) -> str | None:
    """Get a valid access token, refreshing if needed."""
    from app.routers.auth_outlook import load_tokens, refresh_access_token

    tokens = load_tokens(account)
    if not tokens:
        return None

    # Try existing token first; if it fails, we'll refresh
    access_token = tokens.get("access_token")
    if access_token:
        return access_token

    return await refresh_access_token(account)


def _check_account(account: str) -> str | None:
    """Return error string if account is not connected."""
    from app.routers.auth_outlook import load_tokens

    if not settings.microsoft_client_id:
        return "Microsoft app not configured. Ask Harman to set up the app registration."
    if not load_tokens(account):
        return (
            f"The {account} Outlook account is not connected yet. "
            f"Harman needs to visit /auth/outlook?account={account} to log in."
        )
    return None


async def _graph_request(
    method: str,
    path: str,
    account: str,
    json_body: dict | None = None,
    params: dict | None = None,
) -> dict | str:
    """Make a Graph API request. Returns parsed JSON or error string."""
    from app.routers.auth_outlook import refresh_access_token

    token = await _get_token(account)
    if not token:
        return f"No valid token for {account} account. Harman needs to re-authenticate."

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.request(
            method, f"{GRAPH_BASE}{path}",
            headers=headers, json=json_body, params=params,
        )

    # Token expired — refresh and retry once
    if resp.status_code == 401:
        new_token = await refresh_access_token(account)
        if not new_token:
            return "Authentication expired. Harman needs to re-login at /auth/outlook."
        headers["Authorization"] = f"Bearer {new_token}"
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.request(
                method, f"{GRAPH_BASE}{path}",
                headers=headers, json=json_body, params=params,
            )

    if resp.status_code >= 400:
        logger.error(f"Graph API {method} {path}: {resp.status_code} {resp.text[:300]}")
        return f"Outlook API error ({resp.status_code}). This might be a permissions issue."

    if resp.status_code == 204:
        return {}

    return resp.json()


# ── Calendar ────────────────────────────────────────────────────

async def list_events(inp: dict) -> str:
    """List calendar events for a date range."""
    account = inp.get("account", "work")
    if err := _check_account(account):
        return err

    # Default: today
    date_from = inp.get("date_from", datetime.now(SGT).strftime("%Y-%m-%d"))
    days = inp.get("days", 7)
    max_results = min(inp.get("max_results", 10), 25)

    start = f"{date_from}T00:00:00"
    end_dt = datetime.fromisoformat(date_from) + timedelta(days=days)
    end = f"{end_dt.strftime('%Y-%m-%d')}T23:59:59"

    data = await _graph_request(
        "GET", "/me/calendarView",
        account=account,
        params={
            "startDateTime": start,
            "endDateTime": end,
            "$orderby": "start/dateTime",
            "$top": max_results,
            "$select": "subject,start,end,location,attendees,isAllDay",
        },
    )

    if isinstance(data, str):
        return data  # Error message

    events = data.get("value", [])
    if not events:
        return f"No events found from {date_from} for {days} days."

    lines = []
    for ev in events:
        subj = ev.get("subject", "No title")
        start_raw = ev.get("start", {}).get("dateTime", "")
        end_raw = ev.get("end", {}).get("dateTime", "")
        location = ev.get("location", {}).get("displayName", "")
        all_day = ev.get("isAllDay", False)

        # Format times in SGT
        if start_raw:
            try:
                dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(SGT)
                if all_day:
                    time_str = dt.strftime("%A, %B %d (all day)")
                else:
                    end_dt_parsed = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(SGT)
                    time_str = f"{dt.strftime('%A, %B %d, %I:%M %p')} - {end_dt_parsed.strftime('%I:%M %p')}"
            except (ValueError, TypeError):
                time_str = start_raw
        else:
            time_str = "No time"

        line = f"- {subj} | {time_str}"
        if location:
            line += f" | {location}"

        # Attendees
        attendees = ev.get("attendees", [])
        if attendees:
            names = [a.get("emailAddress", {}).get("name", "") for a in attendees[:5]]
            names = [n for n in names if n]
            if names:
                line += f" | with {', '.join(names)}"
                if len(attendees) > 5:
                    line += f" and {len(attendees) - 5} others"

        lines.append(line)

    header = f"Calendar: {len(events)} events from {date_from} ({days} days)"
    return header + "\n" + "\n".join(lines)


async def create_event(inp: dict) -> str:
    """Create a calendar event."""
    account = inp.get("account", "work")
    if err := _check_account(account):
        return err

    subject = inp.get("subject", "Untitled event")
    start_time = inp["start"]  # ISO format: "2026-04-07T06:00:00"
    end_time = inp["end"]      # ISO format: "2026-04-07T08:00:00"
    location = inp.get("location", "")
    attendees = inp.get("attendees", [])

    body = {
        "subject": subject,
        "start": {"dateTime": start_time, "timeZone": "Singapore Standard Time"},
        "end": {"dateTime": end_time, "timeZone": "Singapore Standard Time"},
    }

    if location:
        body["location"] = {"displayName": location}

    if attendees:
        body["attendees"] = [
            {
                "emailAddress": {"address": email},
                "type": "required",
            }
            for email in attendees
        ]

    data = await _graph_request("POST", "/me/events", account=account, json_body=body)

    if isinstance(data, str):
        return data

    event_id = data.get("id", "unknown")
    return f"Event created: '{subject}' on {start_time} (ID: {event_id})"


async def update_event(inp: dict) -> str:
    """Update an existing calendar event."""
    account = inp.get("account", "work")
    if err := _check_account(account):
        return err

    event_id = inp["event_id"]
    updates = {}

    if "subject" in inp:
        updates["subject"] = inp["subject"]
    if "start" in inp:
        updates["start"] = {"dateTime": inp["start"], "timeZone": "Singapore Standard Time"}
    if "end" in inp:
        updates["end"] = {"dateTime": inp["end"], "timeZone": "Singapore Standard Time"}
    if "location" in inp:
        updates["location"] = {"displayName": inp["location"]}

    if not updates:
        return "No changes specified."

    data = await _graph_request("PATCH", f"/me/events/{event_id}", account=account, json_body=updates)

    if isinstance(data, str):
        return data

    return f"Event updated: '{data.get('subject', 'event')}'"


async def delete_event(inp: dict) -> str:
    """Delete a calendar event."""
    account = inp.get("account", "work")
    if err := _check_account(account):
        return err

    event_id = inp["event_id"]
    data = await _graph_request("DELETE", f"/me/events/{event_id}", account=account)

    if isinstance(data, str):
        return data

    return "Event deleted."


# ── Email ───────────────────────────────────────────────────────

async def get_messages(inp: dict) -> str:
    """Fetch emails from Outlook."""
    account = inp.get("account", "work")
    if err := _check_account(account):
        return err

    max_results = min(inp.get("max_results", 10), 25)
    unread_only = inp.get("unread_only", False)
    from_sender = inp.get("from_sender", "")
    folder = inp.get("folder", "inbox")

    # Build filter
    filters = []
    if unread_only:
        filters.append("isRead eq false")
    if from_sender:
        filters.append(f"from/emailAddress/address eq '{from_sender}'")

    params = {
        "$top": max_results,
        "$orderby": "receivedDateTime desc",
        "$select": "subject,from,receivedDateTime,isRead,bodyPreview",
    }
    if filters:
        params["$filter"] = " and ".join(filters)

    path = f"/me/mailFolders/{folder}/messages" if folder != "inbox" else "/me/messages"

    data = await _graph_request("GET", path, account=account, params=params)

    if isinstance(data, str):
        return data

    messages = data.get("value", [])
    if not messages:
        qualifier = "unread " if unread_only else ""
        return f"No {qualifier}emails found."

    lines = []
    unread_count = 0
    for msg in messages:
        subj = msg.get("subject", "(no subject)")
        sender = msg.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
        received = msg.get("receivedDateTime", "")
        is_read = msg.get("isRead", True)
        preview = msg.get("bodyPreview", "")[:120]

        if not is_read:
            unread_count += 1

        # Format time
        if received:
            try:
                dt = datetime.fromisoformat(received.replace("Z", "+00:00")).astimezone(SGT)
                time_str = dt.strftime("%B %d, %I:%M %p")
            except (ValueError, TypeError):
                time_str = received
        else:
            time_str = ""

        status = " [UNREAD]" if not is_read else ""
        line = f"- {subj}{status} | from {sender} | {time_str}\n  {preview}"
        lines.append(line)

    header = f"Email: {len(messages)} messages"
    if unread_count:
        header += f" ({unread_count} unread)"
    return header + "\n" + "\n".join(lines)


async def send_email(inp: dict) -> str:
    """Send an email via Outlook."""
    account = inp.get("account", "work")
    if err := _check_account(account):
        return err

    to = inp["to"]  # Single email or list
    subject = inp["subject"]
    body_text = inp["body"]

    if isinstance(to, str):
        to = [to]

    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in to
            ],
        },
        "saveToSentItems": True,
    }

    data = await _graph_request("POST", "/me/sendMail", account=account, json_body=message)

    if isinstance(data, str):
        return data

    recipients = ", ".join(to)
    return f"Email sent to {recipients}: '{subject}'"


async def mark_read(inp: dict) -> str:
    """Mark an email as read."""
    account = inp.get("account", "work")
    if err := _check_account(account):
        return err

    message_id = inp["message_id"]
    data = await _graph_request(
        "PATCH", f"/me/messages/{message_id}",
        account=account,
        json_body={"isRead": True},
    )

    if isinstance(data, str):
        return data

    return "Email marked as read."
