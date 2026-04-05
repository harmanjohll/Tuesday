"""Morning briefing endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.briefing_service import get_today_briefing, generate_briefing

router = APIRouter(prefix="/briefing", tags=["briefing"])


@router.get("")
async def get_briefing():
    """Get today's morning briefing (if generated)."""
    briefing = await get_today_briefing()
    if briefing is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No briefing for today yet."},
        )
    return briefing


@router.post("/generate")
async def trigger_briefing():
    """Manually trigger briefing generation (for testing)."""
    briefing = await generate_briefing()
    return briefing
