"""
Human-in-the-loop endpoints: sign-off (the downstream caseworker
confirmation, distinct from the witness's own live read-back confirmation),
manual escalation, and cross-witness reconciliation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.agents import orchestrator, reconciliation, signoff_manager
from app.database import get_session
from app.models.db import (
    Case,
    CaseStatus,
    EscalationEvent,
    EscalationSource,
    ReconciliationConflict,
    SignOffEvent,
    WitnessSession,
)
from app.services.vobiz_client import send_escalation_whatsapp

router = APIRouter()


class SignOffRequest(BaseModel):
    signed_off_by: str
    note: str = ""


class EscalateRequest(BaseModel):
    reason: str


@router.post("/cases/{case_id}/signoff")
async def signoff_case(case_id: str, body: SignOffRequest):
    with get_session() as db:
        case = db.get(Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"unknown case_id {case_id!r}")

        try:
            case.status = signoff_manager.transition(case.status, CaseStatus.confirmed)
        except signoff_manager.InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        db.add(case)
        db.add(SignOffEvent(case_id=case_id, signed_off_by=body.signed_off_by, note=body.note))
        db.commit()
        db.refresh(case)
        return case


@router.post("/cases/{case_id}/escalate")
async def escalate_case(case_id: str, body: EscalateRequest):
    with get_session() as db:
        case = db.get(Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"unknown case_id {case_id!r}")

        try:
            case.status = signoff_manager.transition(case.status, CaseStatus.escalated)
        except signoff_manager.InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        db.add(case)
        event = EscalationEvent(case_id=case_id, source=EscalationSource.witness_distress, reason=body.reason)
        db.add(event)
        db.commit()

        sent = await send_escalation_whatsapp(case.reference_code, body.reason, sketch_url=None)
        event.vobiz_message_sent = sent
        db.add(event)
        db.commit()
        db.refresh(case)
        return case


@router.post("/cases/{case_id}/reconcile")
async def reconcile_case(case_id: str):
    with get_session() as db:
        case = db.get(Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"unknown case_id {case_id!r}")

        witness_sessions = db.exec(select(WitnessSession).where(WitnessSession.case_id == case_id)).all()
        if len(witness_sessions) < 2:
            raise HTTPException(status_code=400, detail="reconciliation requires at least two witness sessions")

        # Scope discipline per plan: exactly two witnesses for the demo.
        session_a, session_b = witness_sessions[0], witness_sessions[1]
        params_a = orchestrator.load_current_params(db, session_a.id)
        params_b = orchestrator.load_current_params(db, session_b.id)

        result = await reconciliation.reconcile(params_a, params_b)

        # Supersede any previous unresolved conflicts for this case so only
        # the latest reconciliation run's conflicts show as live.
        previous = db.exec(
            select(ReconciliationConflict).where(
                ReconciliationConflict.case_id == case_id, ReconciliationConflict.resolved == False  # noqa: E712
            )
        ).all()
        for p in previous:
            p.resolved = True
            db.add(p)

        for conflict in result.conflicts:
            db.add(
                ReconciliationConflict(
                    case_id=case_id,
                    field_name=conflict.field_name,
                    witness_a_session_id=session_a.id,
                    witness_a_value=conflict.witness_a_value,
                    witness_b_session_id=session_b.id,
                    witness_b_value=conflict.witness_b_value,
                )
            )

        escalated = False
        if result.conflicts:
            try:
                case.status = signoff_manager.transition(case.status, CaseStatus.escalated)
                escalated = True
            except signoff_manager.InvalidTransition:
                pass  # already escalated or terminal; conflicts are still recorded above
            db.add(
                EscalationEvent(
                    case_id=case_id,
                    source=EscalationSource.reconciliation_conflict,
                    reason=f"{len(result.conflicts)} field(s) disagreed between witnesses",
                )
            )

        db.add(case)
        db.commit()

        return {
            "reconciled": result.reconciled,
            "conflicts": result.conflicts,
            "case_escalated": escalated,
        }
