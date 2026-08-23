"""
Vobiz WhatsApp Business API send, used only for the escalation leg (see
plan: Agora stays the exclusive primary voice channel). If Vobiz isn't
configured (Phase 0 checklist item not completed), escalation still fires
via the in-app banner alone -- this client degrades quietly rather than
raising, since a missing sponsor integration should never block the actual
safety mechanism (escalation itself).
"""

import httpx

from app.config import settings

VOBIZ_BASE_URL = "https://api.vobiz.ai/api/v1"


async def send_escalation_whatsapp(case_reference: str, reason: str, sketch_url: str | None) -> bool:
    if not settings.vobiz_configured:
        return False

    body = (
        f"Case escalation: {case_reference}\n"
        f"Reason: {reason}\n"
        + (f"Sketch: {sketch_url}\n" if sketch_url else "")
        + "This is a draft requiring human review -- not an authoritative identification."
    )

    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            f"{VOBIZ_BASE_URL}/whatsapp/messages",
            headers={
                "X-Auth-ID": settings.vobiz_auth_id,
                "X-Auth-Token": settings.vobiz_auth_token,
            },
            json={
                "to": settings.vobiz_caseworker_whatsapp_number,
                "type": "text",
                "text": {"body": body},
            },
        )
        response.raise_for_status()
        return True
