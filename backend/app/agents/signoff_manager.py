"""
Sign-off Manager: pure state-transition logic for a Case's lifecycle.
OPEN -> PENDING_REVIEW (witness confirmed via confirmation.py, case filed) ->
CONFIRMED (human caseworker signs off) or ESCALATED (distress, unresolved
reconciliation conflict, or classifier failure). No LLM calls here, so no
resilience wrapper needed -- this is deterministic bookkeeping, and its
correctness is exactly what the transition tests below check.
"""

from app.models.db import CaseStatus


class InvalidTransition(Exception):
    pass


_ALLOWED: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.open: {CaseStatus.pending_review, CaseStatus.escalated},
    CaseStatus.pending_review: {CaseStatus.confirmed, CaseStatus.escalated},
    CaseStatus.confirmed: set(),  # terminal for the demo (reopening a signed-off case is explicitly cut, see plan)
    CaseStatus.escalated: {CaseStatus.pending_review},  # a human can resolve an escalation and return it to review
}


def transition(current: CaseStatus, target: CaseStatus) -> CaseStatus:
    if target not in _ALLOWED[current]:
        raise InvalidTransition(f"cannot move case from {current} to {target}")
    return target
