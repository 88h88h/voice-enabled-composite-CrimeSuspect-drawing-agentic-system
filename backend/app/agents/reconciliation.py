"""
Reconciliation Agent: cross-witness comparison, scoped to exactly two
witness sessions per case for the demo (see plan). Compares two
FaceParameters sets field by field -- agreement locks the feature,
disagreement is flagged as an explicit conflict for human review rather
than silently picked one way.

Fails CLOSED: if this agent errors, every filled field on either side
becomes an unresolved conflict rather than being silently merged. This
mirrors the escalation classifier's fail-closed policy -- both agents can
influence what goes into a case file, so uncertainty here defaults to a
human, never to a guess.
"""

from pydantic import BaseModel

from app.models.schema import FaceParameters
from app.services.resilience import run_with_fallback


class FieldConflict(BaseModel):
    field_name: str
    witness_a_value: str
    witness_a_verbatim: str
    witness_b_value: str
    witness_b_verbatim: str


class ReconciliationResult(BaseModel):
    reconciled: FaceParameters
    conflicts: list[FieldConflict]


def _value_str(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _all_conflict_fallback(a: FaceParameters, b: FaceParameters) -> ReconciliationResult:
    """Fail-closed fallback: treat every field either witness filled in as
    an unresolved conflict, reconciled left empty. Safer than guessing."""
    conflicts = []
    for field_name in set(a.filled_fields()) | set(b.filled_fields()):
        conflicts.append(
            FieldConflict(
                field_name=field_name,
                witness_a_value=_value_str(getattr(a, field_name)) if getattr(a, field_name) else "",
                witness_a_verbatim=getattr(a, f"{field_name}_verbatim") or "",
                witness_b_value=_value_str(getattr(b, field_name)) if getattr(b, field_name) else "",
                witness_b_verbatim=getattr(b, f"{field_name}_verbatim") or "",
            )
        )
    return ReconciliationResult(reconciled=FaceParameters(), conflicts=conflicts)


async def reconcile(witness_a: FaceParameters, witness_b: FaceParameters) -> ReconciliationResult:
    async def _call() -> ReconciliationResult:
        reconciled = FaceParameters()
        conflicts: list[FieldConflict] = []

        all_fields = set(witness_a.filled_fields()) | set(witness_b.filled_fields())
        for field_name in all_fields:
            a_val = getattr(witness_a, field_name)
            b_val = getattr(witness_b, field_name)
            verbatim_field = f"{field_name}_verbatim"

            if a_val is not None and b_val is not None:
                if a_val == b_val:
                    setattr(reconciled, field_name, a_val)
                    setattr(reconciled, verbatim_field, getattr(witness_a, verbatim_field))
                else:
                    conflicts.append(
                        FieldConflict(
                            field_name=field_name,
                            witness_a_value=_value_str(a_val),
                            witness_a_verbatim=getattr(witness_a, verbatim_field) or "",
                            witness_b_value=_value_str(b_val),
                            witness_b_verbatim=getattr(witness_b, verbatim_field) or "",
                        )
                    )
            else:
                # only one witness mentioned this feature -- not a conflict,
                # but also not double-confirmed; carry it forward as-is with
                # its single source, still paired with its own verbatim quote
                source_val = a_val if a_val is not None else b_val
                source_verbatim = getattr(witness_a if a_val is not None else witness_b, verbatim_field)
                setattr(reconciled, field_name, source_val)
                setattr(reconciled, verbatim_field, source_verbatim)

        reconciled.distinguishing_marks = list(
            dict.fromkeys(witness_a.distinguishing_marks + witness_b.distinguishing_marks)
        )
        return ReconciliationResult(reconciled=reconciled, conflicts=conflicts)

    fallback = _all_conflict_fallback(witness_a, witness_b)
    return await run_with_fallback(_call, fallback=fallback, agent_name="reconciliation")
