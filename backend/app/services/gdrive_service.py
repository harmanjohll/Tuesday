"""Google Drive API client.

Uses the same OAuth tokens as Gmail (expanded scopes).
Read files, search, and upload documents.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger("tuesday.gdrive")

DRIVE_BASE = "https://www.googleapis.com/drive/v3"
TIMEOUT = 15.0


async def _get_token() -> str | None:
    from app.routers.auth_gmail import load_tokens, refresh_access_token
    tokens = load_tokens()
    if not tokens:
        return None
    return tokens.get("access_token") or await refresh_access_token()


def _check() -> str | None:
    from app.routers.auth_gmail import load_tokens
    from app.config import settings
    if not settings.google_client_id:
        return "Google app not configured."
    if not load_tokens():
        return "Google not connected. Visit /auth/gmail to log in (covers Drive too)."
    return None


async def _drive_request(method: str, path: str, **kwargs) -> dict | str:
    from app.routers.auth_gmail import refresh_access_token
    token = await _get_token()
    if not token:
        return "No valid Google token."

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.request(method, f"{DRIVE_BASE}{path}", headers=headers, **kwargs)

    if resp.status_code == 401:
        new_token = await refresh_access_token()
        if not new_token:
            return "Google auth expired. Re-login at /auth/gmail."
        headers["Authorization"] = f"Bearer {new_token}"
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.request(method, f"{DRIVE_BASE}{path}", headers=headers, **kwargs)

    if resp.status_code not in (200, 201):
        return f"Drive API error: {resp.status_code} {resp.text[:200]}"
    return resp.json()


async def list_files(inp: dict) -> str:
    if err := _check():
        return err

    query = inp.get("query", "")
    max_results = min(inp.get("max_results", 15), 25)
    folder_id = inp.get("folder_id", "")

    q_parts = ["trashed = false"]
    if query:
        q_parts.append(f"name contains '{query}'")
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")

    data = await _drive_request("GET", "/files", params={
        "q": " and ".join(q_parts),
        "pageSize": max_results,
        "fields": "files(id,name,mimeType,modifiedTime,size)",
        "orderBy": "modifiedTime desc",
    })

    if isinstance(data, str):
        return data

    files = data.get("files", [])
    if not files:
        return f"No files found{' matching ' + query if query else ''}."

    lines = [f"Drive files ({len(files)}):"]
    for f in files:
        name = f.get("name", "Untitled")
        mime = f.get("mimeType", "")
        modified = f.get("modifiedTime", "")[:10]
        size = f.get("size", "")
        size_str = f" ({_human_size(int(size))})" if size else ""

        # Simplify mime type
        type_label = mime.split(".")[-1] if "google-apps" in mime else mime.split("/")[-1]
        lines.append(f"- {name} [{type_label}]{size_str} (modified {modified}, id: {f['id'][:12]}...)")

    return "\n".join(lines)


async def read_file(inp: dict) -> str:
    if err := _check():
        return err

    file_id = inp["file_id"]
    token = await _get_token()
    if not token:
        return "No valid Google token."

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # First get file metadata
        meta_resp = await client.get(
            f"{DRIVE_BASE}/files/{file_id}",
            headers=headers,
            params={"fields": "name,mimeType,size"},
        )
        if meta_resp.status_code != 200:
            return f"File not found: {meta_resp.status_code}"

        meta = meta_resp.json()
        mime = meta.get("mimeType", "")
        name = meta.get("name", "file")

        # Google Docs/Sheets/Slides → export as plain text or CSV
        if "google-apps.document" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
            )
        elif "google-apps.spreadsheet" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/csv"},
            )
        elif "google-apps.presentation" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
            )
        else:
            # Regular file — download content
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )

    if resp.status_code != 200:
        return f"Error reading file: {resp.status_code}"

    content = resp.text
    if len(content) > 10000:
        content = content[:10000] + "\n... (truncated)"

    return f"File: {name}\n\n{content}"


async def search_files(inp: dict) -> str:
    """Search Drive files by content or name."""
    if err := _check():
        return err

    query = inp.get("query", "")
    if not query:
        return "No search query provided."

    data = await _drive_request("GET", "/files", params={
        "q": f"fullText contains '{query}' and trashed = false",
        "pageSize": 10,
        "fields": "files(id,name,mimeType,modifiedTime)",
        "orderBy": "modifiedTime desc",
    })

    if isinstance(data, str):
        return data

    files = data.get("files", [])
    if not files:
        return f"No files found containing '{query}'."

    lines = [f"Files matching '{query}' ({len(files)}):"]
    for f in files:
        name = f.get("name", "Untitled")
        modified = f.get("modifiedTime", "")[:10]
        lines.append(f"- {name} (modified {modified}, id: {f['id'][:12]}...)")

    return "\n".join(lines)


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
