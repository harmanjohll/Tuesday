"""Template service — manage PPTX/DOCX templates for document generation.

Harman can upload corporate templates (e.g. school branding) and Tuesday
will use them as the base when generating presentations or documents.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger("tuesday.templates")

_METADATA_FILE = settings.templates_dir / "_templates.json"


def _load_metadata() -> list[dict]:
    if _METADATA_FILE.exists():
        return json.loads(_METADATA_FILE.read_text())
    return []


def _save_metadata(data: list[dict]) -> None:
    settings.templates_dir.mkdir(parents=True, exist_ok=True)
    _METADATA_FILE.write_text(json.dumps(data, indent=2))


async def upload_template(
    file_bytes: bytes,
    original_filename: str,
    name: str = "",
    category: str = "general",
) -> dict:
    """Store a template file and return its metadata."""
    template_id = uuid.uuid4().hex[:12]

    # Determine extension
    ext = Path(original_filename).suffix.lower()
    if ext not in (".pptx", ".docx"):
        return {"error": f"Unsupported template format: {ext}. Use .pptx or .docx"}

    stored_filename = f"{template_id}{ext}"
    path = settings.templates_dir / stored_filename
    path.write_bytes(file_bytes)

    metadata = {
        "id": template_id,
        "name": name or Path(original_filename).stem,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "type": ext.lstrip("."),
        "category": category,
        "size_bytes": len(file_bytes),
    }

    all_meta = _load_metadata()
    all_meta.append(metadata)
    _save_metadata(all_meta)

    logger.info(f"Uploaded template: {metadata['name']} ({template_id})")
    return metadata


def list_templates(template_type: str = "") -> list[dict]:
    """List all available templates, optionally filtered by type."""
    templates = _load_metadata()
    if template_type:
        templates = [t for t in templates if t.get("type") == template_type]
    return templates


def get_template_path(template_id: str) -> Optional[Path]:
    """Get the filesystem path for a template."""
    for t in _load_metadata():
        if t["id"] == template_id:
            path = settings.templates_dir / t["stored_filename"]
            if path.exists():
                return path
    return None


def delete_template(template_id: str) -> bool:
    """Delete a template."""
    all_meta = _load_metadata()
    for i, t in enumerate(all_meta):
        if t["id"] == template_id:
            path = settings.templates_dir / t["stored_filename"]
            if path.exists():
                path.unlink()
            all_meta.pop(i)
            _save_metadata(all_meta)
            return True
    return False
