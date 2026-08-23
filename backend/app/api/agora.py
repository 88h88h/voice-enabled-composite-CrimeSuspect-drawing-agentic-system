"""
Agora session wiring: start/stop the Conversational AI agent for a witness
session, and mint the RTC token the frontend uses to join the same channel.
The agent config itself lives in services/agora_rest.py (code-defined
preset, no Console step) -- this file just exposes it over HTTP for the
frontend to call.
"""

import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import get_session
from app.models.db import WitnessSession
from app.services.agora_rest import build_rtc_token, create_convo_ai_agent, stop_convo_ai_agent

router = APIRouter()

AGENT_UID = 1


class StartAgentRequest(BaseModel):
    case_id: str
    session_id: str


class StopAgentRequest(BaseModel):
    agent_id: str


def _channel_name(case_id: str, session_id: str) -> str:
    return f"case-{case_id}-{session_id}"


@router.post("/agora/agent/start")
async def start_agent(body: StartAgentRequest):
    with get_session() as db:
        witness_session = db.get(WitnessSession, body.session_id)
        if witness_session is None or witness_session.case_id != body.case_id:
            raise HTTPException(status_code=404, detail="session not found for this case")

    channel_name = _channel_name(body.case_id, body.session_id)
    frontend_uid = random.randint(10000, 99999)

    agora_response = await create_convo_ai_agent(body.case_id, body.session_id, channel_name, AGENT_UID)
    frontend_token = build_rtc_token(channel_name, frontend_uid)

    return {
        "app_id": settings.agora_app_id,
        "channel_name": channel_name,
        "frontend_uid": frontend_uid,
        "frontend_token": frontend_token,
        "agent_id": agora_response.get("agent_id"),
    }


@router.post("/agora/agent/stop")
async def stop_agent(body: StopAgentRequest):
    await stop_convo_ai_agent(body.agent_id)
    return {"stopped": True}
