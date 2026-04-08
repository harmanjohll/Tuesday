"""Reflection review endpoints — list, read, approve, generate."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services import reflection_service

router = APIRouter(prefix="/reflections", tags=["reflections"])


@router.get("")
async def list_reflections(limit: int = 10):
    return await reflection_service.list_reflections(limit)


@router.get("/{reflection_id}")
async def get_reflection(reflection_id: str):
    result = await reflection_service.get_reflection(reflection_id)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Reflection not found"})
    return result


@router.post("/{reflection_id}/approve")
async def approve_reflection(reflection_id: str):
    result = await reflection_service.approve_reflection(reflection_id)
    return {"status": result}


@router.post("/generate")
async def trigger_reflection():
    """Manually trigger a reflection (for testing)."""
    result = await reflection_service.generate_weekly_reflection()
    return result
