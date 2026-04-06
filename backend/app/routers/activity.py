"""Activity feed router -- "while you were away" events."""

from fastapi import APIRouter, Query

from app.services.activity_service import get_events_since

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/since")
async def activity_since(ts: str = Query(..., description="ISO timestamp of last seen")):
    events = get_events_since(ts)
    return {"events": events, "count": len(events)}
