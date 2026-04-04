"""Document upload endpoint — PDF, images, and text files.

Accepts file uploads, encodes them for Claude, and returns
content blocks that the frontend includes in chat messages.
"""

from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, HTTPException
from fastapi.responses import FileResponse

from app.config import settings

logger = logging.getLogger("tuesday.documents")

router = APIRouter(prefix="/documents", tags=["documents"])

# Supported MIME types and their Claude content block types
SUPPORTED_TYPES = {
    # Images → Claude vision
    "image/jpeg": "image",
    "image/png": "image",
    "image/gif": "image",
    "image/webp": "image",
    # PDFs → Claude document
    "application/pdf": "document",
    # Text → inline
    "text/plain": "text",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload")
async def upload_document(file: UploadFile):
    """Upload a document for Tuesday to analyse.

    Returns a content block that the frontend includes in the next chat message.
    """
    content_type = file.content_type or "application/octet-stream"

    # Check file type
    block_type = SUPPORTED_TYPES.get(content_type)
    if not block_type:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. "
                   f"Supported: PDF, JPEG, PNG, GIF, WebP, plain text.",
        )

    # Read file
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20MB).")

    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Save to uploads dir for reference
    uploads_dir = settings.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename or "file").suffix
    saved_path = uploads_dir / f"{file_id}{ext}"
    saved_path.write_bytes(data)

    logger.info(f"Uploaded {file.filename} ({content_type}, {len(data)} bytes) → {saved_path.name}")

    # Build Claude content block
    b64_data = base64.standard_b64encode(data).decode("ascii")

    if block_type == "image":
        content_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": content_type,
                "data": b64_data,
            },
        }
    elif block_type == "document":
        content_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": content_type,
                "data": b64_data,
            },
        }
    else:
        # Plain text — just include as text
        text_content = data.decode("utf-8", errors="replace")
        content_block = {
            "type": "text",
            "text": f"[Uploaded file: {file.filename}]\n\n{text_content}",
        }

    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": content_type,
        "size": len(data),
        "content_block": content_block,
    }


# MIME types for generated files
_DOWNLOAD_TYPES = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".csv": "text/csv",
}


@router.get("/download/{file_id}")
async def download_document(file_id: str):
    """Download a generated document by file ID."""
    # Search in both uploads and outputs directories
    for search_dir in [settings.outputs_dir, settings.uploads_dir]:
        if not search_dir.exists():
            continue
        for path in search_dir.iterdir():
            if path.stem == file_id or path.name.startswith(file_id):
                media_type = _DOWNLOAD_TYPES.get(path.suffix, "application/octet-stream")
                return FileResponse(
                    path=str(path),
                    media_type=media_type,
                    filename=path.name,
                )

    raise HTTPException(status_code=404, detail="File not found.")
