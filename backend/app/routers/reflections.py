"""Reflection review endpoints — weekly + micro-reflections."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services import reflection_service

router = APIRouter(prefix="/reflections", tags=["reflections"])


# ======================== Weekly Reflections ========================

@router.get("")
async def list_reflections(limit: int = 10):
    return await reflection_service.list_reflections(limit)


@router.get("/weekly/{reflection_id}")
async def get_reflection(reflection_id: str):
    result = await reflection_service.get_reflection(reflection_id)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Reflection not found"})
    return result


@router.post("/weekly/{reflection_id}/approve")
async def approve_reflection(reflection_id: str):
    result = await reflection_service.approve_reflection(reflection_id)
    return {"status": result}


@router.post("/generate")
async def trigger_reflection():
    """Manually trigger a weekly reflection (for testing)."""
    result = await reflection_service.generate_weekly_reflection()
    return result


# ======================== Micro-Reflections ========================

@router.get("/micro")
async def list_micro_reflections(limit: int = 20):
    return await reflection_service.list_micro_reflections(limit)


@router.get("/micro/{reflection_id}")
async def get_micro_reflection(reflection_id: str):
    result = await reflection_service.get_micro_reflection(reflection_id)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Micro-reflection not found"})
    return result


@router.post("/micro/{reflection_id}/approve")
async def approve_micro_reflection(reflection_id: str):
    result = await reflection_service.approve_micro_reflection(reflection_id)
    return {"status": result}


@router.post("/micro/{reflection_id}/dismiss")
async def dismiss_micro_reflection(reflection_id: str):
    result = await reflection_service.dismiss_micro_reflection(reflection_id)
    return {"status": result}
