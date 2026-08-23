"""
Consistency Agent: within-witness contradiction detection. Compares a newly
extracted delta against what's already locked for this session, and flags
fields where the witness now appears to be saying something different
("close-set" then later "wide-set" for eyes_spacing).

Fails OPEN to "no contradiction" -- non-critical: the worst case of a missed
contradiction is a missed clarifying question, not a wrong action taken, so
it doesn't need the fail-closed treatment Reconciliation/Escalation get.
"""

from pydantic import BaseModel

from app.models.schema import FaceParameters, FeatureDelta
from app.services.resilience import run_with_fallback


class Contradiction(BaseModel):
    field_name: str
    previous_value: str
    previous_verbatim: str
    new_value: str
    new_verbatim: str


class ConsistencyResult(BaseModel):
    contradictions: list[Contradiction] = []


async def check_consistency(locked_params: FaceParameters, delta: FeatureDelta) -> ConsistencyResult:
    """Pure comparison, no LLM call needed -- a contradiction here just means
    'the delta wants to overwrite a field that was already filled with a
    DIFFERENT value.' Correcting a null field isn't a contradiction, it's
    just filling in missing info."""

    async def _call() -> ConsistencyResult:
        found: list[Contradiction] = []
        for field_name in delta.updates.filled_fields():
            previous = getattr(locked_params, field_name)
            new = getattr(delta.updates, field_name)
            if previous is not None and new is not None and previous != new:
                # .value, not str(): for a (str, Enum) member, str() returns
                # "Spacing.close_set" (the member repr), not the actual value
                # "close-set" -- would leak Python-internal names into any
                # UI/log that renders these fields.
                previous_str = previous.value if hasattr(previous, "value") else str(previous)
                new_str = new.value if hasattr(new, "value") else str(new)
                found.append(
                    Contradiction(
                        field_name=field_name,
                        previous_value=previous_str,
                        previous_verbatim=getattr(locked_params, f"{field_name}_verbatim") or "",
                        new_value=new_str,
                        new_verbatim=getattr(delta.updates, f"{field_name}_verbatim") or "",
                    )
                )
        return ConsistencyResult(contradictions=found)

    return await run_with_fallback(_call, fallback=ConsistencyResult(), agent_name="consistency")


def build_clarifying_question(contradiction: Contradiction) -> str:
    field_label = contradiction.field_name.replace("_", " ")
    return (
        f"Earlier you said the {field_label} was '{contradiction.previous_verbatim}', "
        f"just now it sounded like '{contradiction.new_verbatim}' -- which is right?"
    )
