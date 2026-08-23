"""
SQLModel tables. This is the single source of truth for conversation and
case state -- the /chat/completions endpoint treats every request as
stateless and reconstructs context from here, rather than trusting Agora to
replay full history.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _short_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


class CaseStatus(str, Enum):
    open = "OPEN"
    pending_review = "PENDING_REVIEW"
    confirmed = "CONFIRMED"
    escalated = "ESCALATED"


class SessionStatus(str, Enum):
    in_progress = "IN_PROGRESS"
    confirmed_by_witness = "CONFIRMED_BY_WITNESS"


class SketchStatus(str, Enum):
    generating = "GENERATING"
    ready = "READY"
    generation_failed = "GENERATION_FAILED"


class EscalationSource(str, Enum):
    witness_distress = "WITNESS_DISTRESS"
    reconciliation_conflict = "RECONCILIATION_CONFLICT"
    classifier_failure = "CLASSIFIER_FAILURE"


class Case(SQLModel, table=True):
    id: str = Field(default_factory=lambda: _short_id("CASE"), primary_key=True)
    reference_code: str = Field(default_factory=lambda: _short_id("REF"))
    incident_location: str = ""
    incident_description: str = ""
    jurisdiction_name: str = ""
    jurisdiction_contact: str = ""
    status: CaseStatus = CaseStatus.open
    created_at: datetime = Field(default_factory=_now)


class WitnessSession(SQLModel, table=True):
    id: str = Field(default_factory=lambda: _short_id("WIT"), primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    witness_label: str = "Witness 1"
    language_hint: str = ""
    status: SessionStatus = SessionStatus.in_progress
    created_at: datetime = Field(default_factory=_now)


class FeatureVersion(SQLModel, table=True):
    """Append-only per-turn snapshot of a witness session's FaceParameters
    (JSON-serialized). Doubles as an audit trail: every parameter change is
    a real row, not just in-memory conversation state."""

    id: int = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="witnesssession.id", index=True)
    turn_index: int
    parameters_json: str
    created_at: datetime = Field(default_factory=_now)


class ReconciliationConflict(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    field_name: str
    witness_a_session_id: str
    witness_a_value: str
    witness_b_session_id: str
    witness_b_value: str
    resolved: bool = False
    resolution_note: str = ""
    created_at: datetime = Field(default_factory=_now)


class SketchImage(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    session_id: str | None = Field(default=None, foreign_key="witnesssession.id")  # None => case-level reconciled sketch
    file_path: str = ""
    status: SketchStatus = SketchStatus.generating
    created_at: datetime = Field(default_factory=_now)


class SignOffEvent(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    signed_off_by: str = ""
    note: str = ""
    created_at: datetime = Field(default_factory=_now)


class EscalationEvent(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    source: EscalationSource
    reason: str = ""
    vobiz_message_sent: bool = False
    created_at: datetime = Field(default_factory=_now)
