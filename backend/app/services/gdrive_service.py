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
    refreshed = await refresh_access_token()
    return refreshed or tokens.get("access_token")


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

    async with httpx.AsyncClient(timeout=60.0) as client:
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

        # Google-native: export as text
        if "google-apps.document" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
            )
            content = resp.text if resp.status_code == 200 else f"Error exporting: {resp.status_code}"
        elif "google-apps.spreadsheet" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/csv"},
            )
            content = resp.text if resp.status_code == 200 else f"Error exporting: {resp.status_code}"
        elif "google-apps.presentation" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
            )
            content = resp.text if resp.status_code == 200 else f"Error exporting: {resp.status_code}"

        # Uploaded DOCX: download binary + extract text
        elif mime in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            if resp.status_code != 200:
                return f"Error downloading {name}: {resp.status_code}"
            content = _extract_docx_text(resp.content, name)

        # Uploaded PPTX: download binary + extract text
        elif mime in (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        ):
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            if resp.status_code != 200:
                return f"Error downloading {name}: {resp.status_code}"
            content = _extract_pptx_text(resp.content, name)

        # Uploaded PDF: download binary + extract text
        elif mime == "application/pdf":
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            if resp.status_code != 200:
                return f"Error downloading {name}: {resp.status_code}"
            content = _extract_pdf_text(resp.content, name)

        # Plain text: download directly
        elif mime.startswith("text/"):
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            content = resp.text if resp.status_code == 200 else f"Error downloading: {resp.status_code}"

        else:
            return f"Unsupported file type: {mime}"

    if len(content) > 10000:
        content = content[:10000] + "\n... (truncated)"

    return f"File: {name}\n\n{content}"


async def upload_file(inp: dict) -> str:
    """Upload a file to Google Drive."""
    if err := _check():
        return err

    file_path = inp.get("file_path", "")
    folder_name = inp.get("folder_name", "")
    file_name = inp.get("file_name", "")

    from pathlib import Path
    local_path = Path(file_path)
    if not local_path.exists():
        # Try in outputs directory
        from app.config import settings
        local_path = settings.outputs_dir / file_path
        if not local_path.exists():
            return f"File not found: {file_path}"

    if not file_name:
        file_name = local_path.name

    token = await _get_token()
    if not token:
        return "No valid Google token."

    headers = {"Authorization": f"Bearer {token}"}

    # Find target folder if specified
    folder_id = None
    if folder_name:
        data = await _drive_request("GET", "/files", params={
            "q": f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "pageSize": 1,
            "fields": "files(id,name)",
        })
        if isinstance(data, dict):
            folders = data.get("files", [])
            if folders:
                folder_id = folders[0]["id"]

    # Determine MIME type
    suffix = local_path.suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".doc": "application/msword",
        ".ppt": "application/vnd.ms-powerpoint",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    mime_type = mime_map.get(suffix, "application/octet-stream")

    # Upload using multipart upload
    import json as json_module

    metadata = {"name": file_name}
    if folder_id:
        metadata["parents"] = [folder_id]

    file_content = local_path.read_bytes()

    # Use multipart upload (metadata + content)
    boundary = "tuesday_upload_boundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json_module.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_content + f"\r\n--{boundary}--".encode()

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            content=body,
        )

    if resp.status_code in (200, 201):
        result = resp.json()
        name = result.get("name", file_name)
        fid = result.get("id", "unknown")
        location = f" in folder '{folder_name}'" if folder_name else ""
        return f"Uploaded '{name}' to Google Drive{location} (ID: {fid})"
    else:
        return f"Upload failed: {resp.status_code} {resp.text[:200]}"


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


async def list_folder_contents(folder_name: str) -> list[dict] | str:
    """Find a folder by name and list all files in it."""
    if err := _check():
        return err

    # Find the folder
    data = await _drive_request("GET", "/files", params={
        "q": f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        "pageSize": 1,
        "fields": "files(id,name)",
    })
    if isinstance(data, str):
        return data

    folders = data.get("files", [])
    if not folders:
        return f"Folder '{folder_name}' not found in Google Drive."

    folder_id = folders[0]["id"]

    # List files in the folder
    data = await _drive_request("GET", "/files", params={
        "q": f"'{folder_id}' in parents and trashed = false",
        "pageSize": 50,
        "fields": "files(id,name,mimeType,modifiedTime,size)",
        "orderBy": "modifiedTime desc",
    })
    if isinstance(data, str):
        return data

    return data.get("files", [])


async def read_file_extended(file_id: str, max_chars: int = 30000) -> str:
    """Read a file with a higher character limit (for analysis use cases)."""
    if err := _check():
        return err

    token = await _get_token()
    if not token:
        return "No valid Google token."

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        meta_resp = await client.get(
            f"{DRIVE_BASE}/files/{file_id}",
            headers=headers,
            params={"fields": "name,mimeType,size"},
        )

        # Handle token refresh on 401
        if meta_resp.status_code == 401:
            from app.routers.auth_gmail import refresh_access_token
            new_token = await refresh_access_token()
            if not new_token:
                return "Google auth expired. Re-login at /auth/gmail."
            headers["Authorization"] = f"Bearer {new_token}"
            meta_resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"fields": "name,mimeType,size"},
            )

        if meta_resp.status_code != 200:
            return f"Error: file not found ({meta_resp.status_code})"

        meta = meta_resp.json()
        mime = meta.get("mimeType", "")
        name = meta.get("name", "file")

        # --- Google-native formats: export as plain text ---
        if "google-apps.document" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
            )
            if resp.status_code == 200:
                content = resp.text
            else:
                return f"Error: could not export {name} ({resp.status_code})"

        elif "google-apps.spreadsheet" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/csv"},
            )
            if resp.status_code == 200:
                content = resp.text
            else:
                return f"Error: could not export {name} ({resp.status_code})"

        elif "google-apps.presentation" in mime:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
            )
            if resp.status_code == 200:
                content = resp.text
            else:
                return f"Error: could not export {name} ({resp.status_code})"

        # --- Uploaded DOCX: download binary + extract text ---
        elif mime in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            if resp.status_code != 200:
                return f"Error: could not download {name} ({resp.status_code})"
            content = _extract_docx_text(resp.content, name)

        # --- Uploaded PPTX: download binary + extract text ---
        elif mime in (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        ):
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            if resp.status_code != 200:
                return f"Error: could not download {name} ({resp.status_code})"
            content = _extract_pptx_text(resp.content, name)

        # --- Uploaded PDF: download binary + extract text ---
        elif mime == "application/pdf":
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            if resp.status_code != 200:
                return f"Error: could not download {name} ({resp.status_code})"
            content = _extract_pdf_text(resp.content, name)

        # --- Plain text files: download directly ---
        elif mime.startswith("text/"):
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
            if resp.status_code != 200:
                return f"Error: could not download {name} ({resp.status_code})"
            content = resp.text

        else:
            return f"Skipped {name}: unsupported file type ({mime})"

    if len(content) > max_chars:
        content = content[:max_chars] + "\n... (truncated)"

    return f"=== {name} ===\n{content}"


def _extract_docx_text(data: bytes, name: str) -> str:
    """Extract text from a DOCX file's binary content."""
    try:
        import io
        from docx import Document
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs) if paragraphs else f"(No readable text in {name})"
    except Exception as e:
        logger.error(f"DOCX extraction failed for {name}: {e}")
        return f"(Could not extract text from {name}: {e})"


def _extract_pptx_text(data: bytes, name: str) -> str:
    """Extract text from a PPTX file's binary content."""
    try:
        import io
        from pptx import Presentation
        prs = Presentation(io.BytesIO(data))
        slides_text = []
        for i, slide in enumerate(prs.slides, 1):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        if para.text.strip():
                            texts.append(para.text.strip())
            if texts:
                slides_text.append(f"[Slide {i}]\n" + "\n".join(texts))
        return "\n\n".join(slides_text) if slides_text else f"(No readable text in {name})"
    except Exception as e:
        logger.error(f"PPTX extraction failed for {name}: {e}")
        return f"(Could not extract text from {name}: {e})"


def _extract_pdf_text(data: bytes, name: str) -> str:
    """Extract text from a PDF file's binary content."""
    try:
        import io
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages_text = []
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text and text.strip():
                pages_text.append(f"[Page {i}]\n{text.strip()}")
        return "\n\n".join(pages_text) if pages_text else f"(No readable text in {name} — may be a scanned image PDF)"
    except Exception as e:
        logger.error(f"PDF extraction failed for {name}: {e}")
        return f"(Could not extract text from {name}: {e})"


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
