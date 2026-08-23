import pytest

from app.agents.signoff_manager import InvalidTransition, transition
from app.models.db import CaseStatus


def test_normal_lifecycle():
    assert transition(CaseStatus.open, CaseStatus.pending_review) == CaseStatus.pending_review
    assert transition(CaseStatus.pending_review, CaseStatus.confirmed) == CaseStatus.confirmed


def test_escalation_and_return_to_review():
    assert transition(CaseStatus.open, CaseStatus.escalated) == CaseStatus.escalated
    assert transition(CaseStatus.pending_review, CaseStatus.escalated) == CaseStatus.escalated
    assert transition(CaseStatus.escalated, CaseStatus.pending_review) == CaseStatus.pending_review


def test_confirmed_is_terminal():
    with pytest.raises(InvalidTransition):
        transition(CaseStatus.confirmed, CaseStatus.open)


def test_cannot_skip_pending_review():
    with pytest.raises(InvalidTransition):
        transition(CaseStatus.open, CaseStatus.confirmed)
