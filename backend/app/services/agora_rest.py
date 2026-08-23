"""
Agora integration, entirely code-driven -- no Console/Studio point-and-click
step for agent configuration (see plan). Two responsibilities:

1. RTC token minting for the frontend to join the voice channel.
2. Conversational AI agent lifecycle via Agora's REST API, with ASR/LLM/TTS
   wiring built as a config object here rather than clicked together in a
   dashboard.

UPDATE: field shapes below are now verified against a real account (the
user's live Studio console, both the "Full REST" code-generation panel and
the official join API docs), not just guessed from generic docs. Confirmed:
- channel/token/agent_rtc_uid/remote_rtc_uids live inside "properties",
  alongside asr/llm/tts -- matches what was already here.
- Custom LLM (pointing at our own server) uses {"url", "api_key",
  "system_messages", ...} -- confirmed via docs.agora.io's custom-LLM page.
  This is a DIFFERENT shape than a preset vendor's {"vendor", "params"}
  block; don't mix them.
- "Agora Managed Key" (no separate vendor account needed) is expressed as
  "credential_mode": "managed" inside a vendor block -- confirmed via the
  official join API docs, not the resource_id values Studio's UI shows
  (those looked pipeline-specific, not safely reusable from a raw call).
- TTS uses Minimax with credential_mode=managed instead of ElevenLabs --
  eliminates a whole separate account/signup for the demo.
- ASR uses Deepgram with credential_mode=managed specifically because it's
  the vendor confirmed present in the user's account via a real Full REST
  example; "agora" as the ARES vendor string is a reasonable inference from
  general docs but wasn't directly confirmed the same way, so the
  lower-risk proven option was chosen for Phase 1. Swap to ARES later if
  it's confirmed to work equally simply.
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
            "enable_string_uid": False,
            "idle_timeout": 600,  # auto-cleanup an abandoned session after 10 minutes
            "asr": {
                "vendor": "deepgram",
                "credential_mode": "managed",  # Agora-managed credential, no separate Deepgram account
                "params": {"model": "nova-3", "language": "en"},
            },
            "llm": {
                # Custom LLM shape (our own server), NOT the vendor+managed
                # shape used for asr/tts above -- confirmed these are two
                # distinct, non-interchangeable configurations.
                "url": f"{settings.public_base_url}/chat/completions?session_id={session_id}&case_id={case_id}",
                "api_key": "unused",  # our endpoint doesn't check this; required field for some SDK versions
                "system_messages": [],  # system prompt is owned by elicitation.py, not duplicated here
                "greeting_message": "Hi, I'm here to help build a description of the person you saw. Take your time.",
                "failure_message": "Sorry, one moment please.",  # Agora's own spoken fallback if OUR endpoint is unreachable/times out
                "max_history": 0,  # we reconstruct context from the DB every turn, not from Agora's replay
            },
            "tts": {
                "vendor": "minimax",
                "credential_mode": "managed",  # Agora-managed credential, no separate ElevenLabs/Minimax account needed
                "params": {"model": "speech-2.8-turbo", "voice_setting": {"voice_id": "English_radiant_girl"}},
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
