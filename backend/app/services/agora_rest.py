"""
Agora integration, entirely code-driven -- no Console/Studio point-and-click
step for agent configuration (see plan). Two responsibilities:

1. RTC token minting for the frontend to join the voice channel.
2. Conversational AI agent lifecycle via Agora's REST API, with ASR/LLM/TTS
   wiring built as a config object here rather than clicked together in a
   dashboard.

CAVEAT, stated honestly: the buildTokenWithUid() signature below was
verified against the installed `agora-token-builder` package (see git log --
confirmed by inspecting the real function signature). The CreateConvoAIAgent
request/response shape was NOT verified against a live account (no API
keys available while writing this) -- it's built from Agora's documented
REST contract (OpenAI-compatible llm.url, vendor-keyed asr/tts blocks,
Basic Auth with customer_id:customer_secret). Re-verify the exact field
names against https://docs.agora.io/en/conversational-ai/rest-api/agent/join
as the very first thing in Phase 1 of the build, using a real account --
this file is the single highest-uncertainty piece of the whole system and
is scheduled first in the plan specifically so this gets surfaced with
maximum runway left to fix it.
"""

from __future__ import annotations

import base64
import time

import httpx
from agora_token_builder import RtcTokenBuilder

from app.config import settings

AGORA_REST_BASE = "https://api.agora.io/api/conversational-ai-agent/v2/projects"

RTC_ROLE_PUBLISHER = 1
TOKEN_TTL_SECONDS = 3600


def build_rtc_token(channel_name: str, uid: int) -> str:
    expire_ts = int(time.time()) + TOKEN_TTL_SECONDS
    return RtcTokenBuilder.buildTokenWithUid(
        settings.agora_app_id,
        settings.agora_app_certificate,
        channel_name,
        uid,
        RTC_ROLE_PUBLISHER,
        expire_ts,
    )


def _basic_auth_header() -> str:
    raw = f"{settings.agora_customer_id}:{settings.agora_customer_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _agent_config(case_id: str, session_id: str, channel_name: str, agent_uid: int) -> dict:
    """The code-defined 'preset/template' for agent behavior -- everything
    here is version-controlled, not a Console setting. llm.url embeds the
    session_id so /chat/completions can reconstruct context statelessly."""
    return {
        "name": f"witness-agent-{session_id}",
        "properties": {
            "channel": channel_name,
            "token": build_rtc_token(channel_name, agent_uid),
            "agent_rtc_uid": str(agent_uid),
            "remote_rtc_uids": ["*"],
            "asr": {"vendor": "agora", "language": "auto"},  # Agora ARES: zero-config, 36 languages
            "llm": {
                "url": f"{settings.public_base_url}/chat/completions?session_id={session_id}&case_id={case_id}",
                "api_key": "unused",  # our endpoint doesn't check this; required field for some SDK versions
                "system_messages": [],  # system prompt is owned by elicitation.py, not duplicated here
                "greeting_message": "Hi, I'm here to help build a description of the person you saw. Take your time.",
                "max_history": 0,  # we reconstruct context from the DB every turn, not from Agora's replay
            },
            "tts": {
                "vendor": "elevenlabs",
                "params": {"key": settings.elevenlabs_api_key, "voice_id": settings.elevenlabs_voice_id},
            },
            "advanced_features": {"enable_aivad": True},  # Agora's voice-activity detection -> better barge-in
        },
    }


async def create_convo_ai_agent(case_id: str, session_id: str, channel_name: str, agent_uid: int) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{AGORA_REST_BASE}/{settings.agora_app_id}/join",
            headers={"Authorization": _basic_auth_header(), "Content-Type": "application/json"},
            json=_agent_config(case_id, session_id, channel_name, agent_uid),
        )
        response.raise_for_status()
        return response.json()


async def stop_convo_ai_agent(agent_id: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{AGORA_REST_BASE}/{settings.agora_app_id}/agents/{agent_id}/leave",
            headers={"Authorization": _basic_auth_header()},
        )
        response.raise_for_status()
