"""Writing pipeline — enforces Matthew → Drive → Loki at code level.

When Tuesday receives a writing task, this service orchestrates:
1. Matthew drafts the content (background task, waits for completion)
2. Document auto-saved to Google Drive
3. Loki reviews the draft (background task, waits for completion)
4. Returns a concise summary with Drive link + Loki's feedback
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.config import settings

logger = logging.getLogger("tuesday.pipeline")

SGT = timezone(timedelta(hours=8))


# Module-level pipeline status for real-time tracking
_pipeline_status: str = ""


def get_pipeline_status() -> str:
    """Get current pipeline step — polled by the main chat loop."""
    return _pipeline_status


async def run_writing_pipeline(task: str) -> dict:
    """Orchestrate: Matthew drafts → auto-save to Drive → Loki reviews.

    Returns dict with: draft, drive_link, review, summary.
    """
    global _pipeline_status
    from app.services import agent_service

    logger.info(f"Writing pipeline started: {task[:80]}")

    from app.services.activity_tracker import record_event

    # Step 1: Assign Matthew
    _pipeline_status = "Matthew is drafting..."
    record_event("pipeline_step", agent="Matthew", message="Drafting started")
    matthew_id = _get_agent_id_by_name("Matthew")
    if not matthew_id:
        _pipeline_status = ""
        return _error("Agent 'Matthew' not found. Check Mind Castle agents.")

    await agent_service.assign_task(matthew_id, task)
    logger.info("Pipeline: Matthew assigned")

    # Step 2: Wait for Matthew (poll with backoff, max 120s)
    draft = await _wait_for_agent(matthew_id, timeout=120)
    if not draft or len(draft.strip()) < 20:
        _pipeline_status = ""
        return _error("Matthew produced no usable output.")
    logger.info(f"Pipeline: Matthew done ({len(draft)} chars)")

    # Step 3: Auto-save to Drive
    _pipeline_status = "Saving to Google Drive..."
    record_event("pipeline_step", agent="Matthew", message="Draft complete, saving to Drive")
    drive_link = await _save_to_drive(draft, task)
    logger.info(f"Pipeline: Saved to Drive — {drive_link}")

    # Step 4: Assign Loki to review
    loki_id = _get_agent_id_by_name("Loki")
    if not loki_id:
        _pipeline_status = ""
        return {
            "draft": draft,
            "drive_link": drive_link,
            "review": "(Loki not available for review)",
            "summary": _build_summary(draft, drive_link, "Review skipped — Loki agent not found."),
        }

    _pipeline_status = "Loki is reviewing..."
    record_event("pipeline_step", agent="Loki", message="Reviewing draft")
    review_brief = (
        "Review this draft for weaknesses, gaps, tone issues, and improvements. "
        "Be specific and constructive. Max 200 words.\n\n"
        f"Draft:\n{draft[:3000]}"
    )
    await agent_service.assign_task(loki_id, review_brief)
    logger.info("Pipeline: Loki assigned for review")

    # Step 5: Wait for Loki
    review = await _wait_for_agent(loki_id, timeout=90)
    logger.info(f"Pipeline: Loki done ({len(review)} chars)")

    # Step 6: Build summary
    _pipeline_status = ""
    summary = _build_summary(draft, drive_link, review)
    logger.info("Pipeline: Complete")

    return {"draft": draft, "drive_link": drive_link, "review": review, "summary": summary}


def _get_agent_id_by_name(name: str) -> str | None:
    from app.services import agent_service
    for agent in agent_service._store.list_all():
        if agent.name.lower() == name.lower():
            return agent.id
    return None


async def _wait_for_agent(agent_id: str, timeout: int = 120) -> str:
    """Poll agent status until done, with backoff."""
    from app.services import agent_service

    elapsed = 0
    interval = 3
    while elapsed < timeout:
        agent = agent_service._store.load(agent_id)
        if agent and agent.status in ("done", "needs_review", "failed", "idle", "error"):
            output = agent_service.get_agent_output(agent_id)
            if output and "not found" not in output.lower():
                return output
            # Agent finished but no output — might still be saving
            if agent.status != "working":
                return output or ""
        await asyncio.sleep(interval)
        elapsed += interval
        interval = min(interval * 1.5, 10)

    # Timeout — return whatever we have
    return agent_service.get_agent_output(agent_id) or ""


async def _save_to_drive(content: str, task: str) -> str:
    """Save content as .docx and upload to Google Drive."""
    try:
        from app.services import document_generator, gdrive_service

        # Generate filename from task
        now = datetime.now(SGT)
        words = [w for w in task.split()[:5] if w.isalnum()]
        name_part = "_".join(words)[:30] or "document"
        title = f"{name_part}_{now.strftime('%Y%m%d')}"

        # Create the Word document
        sections = [{"heading": "", "body": content}]
        doc_result = await document_generator.create_word_document({
            "title": title,
            "sections": sections,
        })

        # Extract the file path from DOWNLOAD: link
        path_match = re.search(r"DOWNLOAD:/documents/download/([^\|]+)", doc_result)
        if not path_match:
            return f"Document created locally: {doc_result}"

        file_id = path_match.group(1)
        local_path = settings.outputs_dir / f"{file_id}.docx"

        if not local_path.exists():
            return f"Document created but file not found for upload: {doc_result}"

        # Upload to Google Drive
        upload_result = await gdrive_service.upload_file({
            "file_path": str(local_path),
            "filename": f"{title}.docx",
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        })

        return upload_result

    except Exception as e:
        logger.error(f"Drive save failed: {e}")
        return f"(Drive upload failed: {e})"


def _build_summary(draft: str, drive_link: str, review: str) -> str:
    """Build a concise summary for the chat response."""
    # Preview: first 2 sentences of draft
    sentences = re.split(r'(?<=[.!?])\s+', draft.strip())
    preview = " ".join(sentences[:2])[:200]

    # Loki's key points
    review_sentences = re.split(r'(?<=[.!?])\s+', review.strip())
    review_summary = " ".join(review_sentences[:3])[:300]

    return (
        f"Draft complete. {preview}\n\n"
        f"Saved to Drive: {drive_link}\n\n"
        f"Loki's review: {review_summary}"
    )


def _error(msg: str) -> dict:
    return {"draft": "", "drive_link": "", "review": "", "summary": f"Pipeline error: {msg}"}
