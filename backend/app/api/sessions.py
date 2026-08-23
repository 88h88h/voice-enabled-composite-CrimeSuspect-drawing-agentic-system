"""
Case and witness-session lifecycle endpoints, plus the polling endpoint the
frontend uses to render live state (sketch, parameters with verified vs.
AI-interpreted pairing, conflicts, escalations).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.agents import orchestrator, service_lookup
from app.database import get_session
from app.models.db import (
    Case,
    EscalationEvent,
    ReconciliationConflict,
    SketchImage,
    SketchStatus,
    WitnessSession,
)
from app.services.image_store import sketch_url_for

router = APIRouter()


class CreateCaseRequest(BaseModel):
    incident_location: str
    incident_description: str = ""


class CreateSessionRequest(BaseModel):
    witness_label: str = "Witness 1"
    language_hint: str = ""


@router.post("/cases")
async def create_case(body: CreateCaseRequest):
    jurisdiction = await service_lookup.find_jurisdiction(body.incident_location)
    with get_session() as db:
        case = Case(
            incident_location=body.incident_location,
            incident_description=body.incident_description,
            jurisdiction_name=jurisdiction.jurisdiction_name,
            jurisdiction_contact=jurisdiction.jurisdiction_contact,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case


@router.post("/cases/{case_id}/sessions")
async def create_witness_session(case_id: str, body: CreateSessionRequest):
    with get_session() as db:
        case = db.get(Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"unknown case_id {case_id!r}")

        witness_session = WitnessSession(
            case_id=case_id, witness_label=body.witness_label, language_hint=body.language_hint
        )
        db.add(witness_session)
        db.commit()
        db.refresh(witness_session)
        return witness_session


@router.get("/cases/{case_id}/state")
async def get_case_state(case_id: str):
    with get_session() as db:
        case = db.get(Case, case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"unknown case_id {case_id!r}")

        witness_sessions = db.exec(select(WitnessSession).where(WitnessSession.case_id == case_id)).all()
        sketches = db.exec(
            select(SketchImage).where(SketchImage.case_id == case_id).order_by(SketchImage.created_at.desc())
        ).all()
        conflicts = db.exec(select(ReconciliationConflict).where(ReconciliationConflict.case_id == case_id)).all()
        escalations = db.exec(select(EscalationEvent).where(EscalationEvent.case_id == case_id)).all()

        witnesses_out = []
        for ws in witness_sessions:
            params = orchestrator.load_current_params(db, ws.id)
            latest_sketch = next((s for s in sketches if s.session_id == ws.id), None)
            latest_sketch_url = (
                sketch_url_for(latest_sketch.file_path)
                if latest_sketch and latest_sketch.status == SketchStatus.ready
                else None
            )
            witnesses_out.append(
                {
                    "session": ws,
                    "parameters": params,
                    "latest_sketch_status": latest_sketch.status if latest_sketch else None,
                    "latest_sketch_url": latest_sketch_url,
                }
            )

        return {
            "case": case,
            "witnesses": witnesses_out,
            "conflicts": [c for c in conflicts if not c.resolved],
            "escalations": escalations,
        }
