"""Mind Castle — Agent management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from sse_starlette.sse import EventSourceResponse

from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


class CreateAgentRequest(BaseModel):
    name: str
    role: str
    color: Optional[str] = ""
    system_prompt: Optional[str] = ""


class AssignTaskRequest(BaseModel):
    task: str


class ChatRequest(BaseModel):
    message: str


@router.post("")
async def create_agent(req: CreateAgentRequest):
    agent = agent_service.create_agent(
        name=req.name,
        role=req.role,
        color=req.color,
        system_prompt=req.system_prompt,
    )
    return agent.to_dict()


@router.get("")
async def list_agents():
    return agent_service.list_agents()


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    if not agent_service.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted"}


@router.post("/{agent_id}/tasks")
async def assign_task(agent_id: str, req: AssignTaskRequest):
    result = await agent_service.assign_task(agent_id, req.task)
    return {"status": result}


@router.get("/{agent_id}/status")
async def get_status(agent_id: str):
    return agent_service.get_agent_status(agent_id)


@router.post("/{agent_id}/chat")
async def chat_with_agent(agent_id: str, req: ChatRequest):
    """Stream a conversation with a specific agent."""
    agent = agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return EventSourceResponse(
        agent_service.chat_with_agent(agent_id, req.message)
    )
