"""Gmail API client for reading and sending personal email.

All methods return human-readable strings (not JSON) so Claude
can synthesize them into natural speech. Email content is never
persisted to disk — only held in memory for the active request.
"""

from __future__ import annotations

import base64
import email.mime.text
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

logger = logging.getLogger("tuesday.gmail")

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
TIMEOUT = 15.0
SGT = timezone(timedelta(hours=8))


async def _get_token() -> str | None:
    """Get a valid access token, refreshing if needed."""
    from app.routers.auth_gmail import load_tokens, refresh_access_token

    tokens = load_tokens()
    if not tokens:
        return None

    access_token = tokens.get("access_token")
    if access_token:
        return access_token

    return await refresh_access_token()


def _check_account() -> str | None:
    """Return error string if Gmail is not connected."""
    from app.routers.auth_gmail import load_tokens

    if not settings.google_client_id:
        return "Google app not configured. Ask Harman to set up Google OAuth."
    if not load_tokens():
        return "Gmail is not connected yet. Harman needs to visit /auth/gmail to log in."
    return None


async def _gmail_request(
    method: str,
    path: str,
    json_body: dict | None = None,
    params: dict | None = None,
) -> dict | str:
    """Make a Gmail API request. Returns parsed JSON or error string."""
    from app.routers.auth_gmail import refresh_access_token

    token = await _get_token()
    if not token:
        return "No valid Gmail token. Harman needs to re-authenticate at /auth/gmail."

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.request(
            method, f"{GMAIL_BASE}{path}",
            headers=headers, json=json_body, params=params,
        )

    # Token expired — refresh and retry once
    if resp.status_code == 401:
        new_token = await refresh_access_token()
        if not new_token:
            return "Gmail authentication expired. Harman needs to re-login at /auth/gmail."
        headers["Authorization"] = f"Bearer {new_token}"
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.request(
                method, f"{GMAIL_BASE}{path}",
                headers=headers, json=json_body, params=params,
            )

    if resp.status_code >= 400:
        logger.error(f"Gmail API {method} {path}: {resp.status_code} {resp.text[:300]}")
        return f"Gmail API error ({resp.status_code}). This might be a permissions issue."

    if resp.status_code == 204:
        return {}

    return resp.json()


def _decode_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    # Simple message (no parts)
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # Multipart — look for text/plain part
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

    # Nested multipart
    for part in payload.get("parts", []):
        if part.get("mimeType", "").startswith("multipart/"):
            result = _decode_body(part)
            if result:
                return result

    return "(no readable text content)"


def _get_header(headers: list, name: str) -> str:
    """Get a header value by name from Gmail headers list."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


# ── Email operations ─────────────────────────────────────────

async def get_messages(inp: dict) -> str:
    """Fetch emails from Gmail."""
    if err := _check_account():
        return err

    max_results = min(inp.get("max_results", 10), 25)
    unread_only = inp.get("unread_only", False)
    from_sender = inp.get("from_sender", "")

    # Build Gmail search query
    q_parts = []
    if unread_only:
        q_parts.append("is:unread")
    if from_sender:
        q_parts.append(f"from:{from_sender}")
    q = " ".join(q_parts) if q_parts else None

    # Step 1: List message IDs
    params = {"maxResults": max_results}
    if q:
        params["q"] = q

    data = await _gmail_request("GET", "/messages", params=params)
    if isinstance(data, str):
        return data

    message_ids = [m["id"] for m in data.get("messages", [])]
    if not message_ids:
        qualifier = "unread " if unread_only else ""
        return f"No {qualifier}emails found."

    # Step 2: Fetch each message's details
    lines = []
    unread_count = 0
    for msg_id in message_ids:
        msg_data = await _gmail_request(
            "GET", f"/messages/{msg_id}",
            params={"format": "full"},
        )
        if isinstance(msg_data, str):
            continue

        headers = msg_data.get("payload", {}).get("headers", [])
        subject = _get_header(headers, "Subject") or "(no subject)"
        sender = _get_header(headers, "From")
        date_str = _get_header(headers, "Date")
        labels = msg_data.get("labelIds", [])
        is_unread = "UNREAD" in labels

        if is_unread:
            unread_count += 1

        # Extract preview from snippet (Gmail provides this)
        preview = msg_data.get("snippet", "")[:120]

        # Parse sender name
        if "<" in sender:
            sender_name = sender.split("<")[0].strip().strip('"')
        else:
            sender_name = sender

        # Format date
        time_str = date_str  # Fallback to raw date string
        try:
            # Gmail dates are RFC 2822 format
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str).astimezone(SGT)
            time_str = dt.strftime("%B %d, %I:%M %p")
        except (ValueError, TypeError):
            pass

        status = " [UNREAD]" if is_unread else ""
        line = f"- {subject}{status} | from {sender_name} | {time_str} [id:{msg_id}]\n  {preview}"
        lines.append(line)

    header = f"Gmail: {len(lines)} messages"
    if unread_count:
        header += f" ({unread_count} unread)"
    return header + "\n" + "\n".join(lines)


async def mark_read(inp: dict) -> str:
    """Mark emails as read."""
    if err := _check_account():
        return err

    message_ids = inp.get("message_ids", [])
    if not message_ids:
        return "No message IDs provided."

    count = 0
    for msg_id in message_ids:
        result = await _gmail_request(
            "POST", f"/messages/{msg_id}/modify",
            json_body={"removeLabelIds": ["UNREAD"]},
        )
        if not isinstance(result, str):
            count += 1

    return f"Marked {count} email(s) as read."


async def archive(inp: dict) -> str:
    """Archive emails (remove from inbox, keep in All Mail)."""
    if err := _check_account():
        return err

    message_ids = inp.get("message_ids", [])
    if not message_ids:
        return "No message IDs provided."

    count = 0
    for msg_id in message_ids:
        result = await _gmail_request(
            "POST", f"/messages/{msg_id}/modify",
            json_body={"removeLabelIds": ["INBOX"]},
        )
        if not isinstance(result, str):
            count += 1

    return f"Archived {count} email(s)."


async def trash(inp: dict) -> str:
    """Move emails to trash."""
    if err := _check_account():
        return err

    message_ids = inp.get("message_ids", [])
    if not message_ids:
        return "No message IDs provided."

    count = 0
    for msg_id in message_ids:
        result = await _gmail_request("POST", f"/messages/{msg_id}/trash")
        if not isinstance(result, str):
            count += 1

    return f"Moved {count} email(s) to trash."


async def send_email(inp: dict) -> str:
    """Send an email via Gmail."""
    if err := _check_account():
        return err

    to = inp["to"]
    subject = inp["subject"]
    body_text = inp["body"]

    # Build MIME message
    msg = email.mime.text.MIMEText(body_text)
    msg["to"] = to
    msg["subject"] = subject

    # Base64url encode the MIME message
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    data = await _gmail_request("POST", "/messages/send", json_body={"raw": raw})

    if isinstance(data, str):
        return data

    return f"Email sent to {to}: '{subject}'"
