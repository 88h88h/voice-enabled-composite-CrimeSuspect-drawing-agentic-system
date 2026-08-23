"""
Service/Jurisdiction Lookup Agent: retrieval of relevant service information
(the incident's location -> the correct police jurisdiction to route the
case to). Thin agent-layer wrapper around jurisdiction_data's static table;
kept as its own module so the orchestrator treats it like any other agent
step (same resilience wrapper, same place in the turn sequence), even
though the lookup itself is trivial for the demo.
"""

from pydantic import BaseModel

from app.services.jurisdiction_data import lookup_jurisdiction
from app.services.resilience import run_with_fallback


class JurisdictionInfo(BaseModel):
    jurisdiction_name: str
    jurisdiction_contact: str


_UNKNOWN = JurisdictionInfo(jurisdiction_name="Unknown -- needs manual routing", jurisdiction_contact="")


async def find_jurisdiction(incident_location: str) -> JurisdictionInfo:
    async def _call() -> JurisdictionInfo:
        name, contact = lookup_jurisdiction(incident_location)
        return JurisdictionInfo(jurisdiction_name=name, jurisdiction_contact=contact)

    return await run_with_fallback(_call, fallback=_UNKNOWN, agent_name="service_lookup", timeout_s=2.0, retries=0)
