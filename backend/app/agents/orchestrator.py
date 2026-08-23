"""
Orchestrator: per-turn glue. Owns DB reads/writes for a witness session's
turn (the DB is the source of truth, never in-memory conversation state,
since Agora's /chat/completions calls are treated as stateless -- see
plan). Sequences: safety guard -> (confirmation classification, if
awaiting) -> extraction+reply (one combined Gemini call) -> consistency ->
apply/persist -> deterministic clarifying question, read-back, or the
model's own reply.

extraction.process_turn() does both feature extraction AND reply
composition in a single Gemini call (see that module's docstring for why:
9-13s sequential became one round-trip). The determinism guarantees for
contradictions and completion read-backs are unaffected -- this orchestrator
still overrides reply_text for those cases regardless of what the model
said, exactly as before the merge.

Deliberately a plain async function, not a graph framework -- the actual
control flow here is a short linear pipeline with a couple of conditional
branches, which is simpler to write correctly and debug live than standing
up a new framework's execution model under an 8-hour clock.
"""

from dataclasses import dataclass

from sqlmodel import Session, select

from app.agents import confirmation, consistency, extraction, safety_guard
from app.agents.extraction import apply_delta
from app.models.db import (
    CaseStatus,
    EscalationEvent,
    EscalationSource,
    FeatureVersion,
    SessionStatus,
    TurnTrace,
    WitnessSession,
)
from app.models.schema import FaceParameters
from app.services.resilience import trace_session


@dataclass
class TurnResult:
    reply_text: str
    witness_confirmed_case: bool = False
    injection_blocked: bool = False


def load_current_params(db: Session, session_id: str) -> FaceParameters:
    latest = db.exec(
        select(FeatureVersion)
        .where(FeatureVersion.session_id == session_id)
        .order_by(FeatureVersion.turn_index.desc())
    ).first()
    if latest is None:
        return FaceParameters()
    return FaceParameters.model_validate_json(latest.parameters_json)


def _persist_feature_version(db: Session, session_id: str, turn_index: int, params: FaceParameters) -> None:
    db.add(
        FeatureVersion(
            session_id=session_id,
            turn_index=turn_index,
            parameters_json=params.model_dump_json(),
        )
    )


def _persist_traces(db: Session, session_id: str, turn_index: int, records) -> None:
    for r in records:
        db.add(
            TurnTrace(
                session_id=session_id,
                turn_index=turn_index,
                agent_name=r.agent_name,
                duration_ms=r.duration_ms,
                used_fallback=r.used_fallback,
                attempts=r.attempts,
            )
        )


async def handle_turn(db: Session, witness_session: WitnessSession, latest_utterance: str) -> TurnResult:
    with trace_session() as traces:
        result = await _handle_turn_inner(db, witness_session, latest_utterance)

    witness_session.turn_count += 1
    db.add(witness_session)
    _persist_traces(db, witness_session.id, witness_session.turn_count, traces)
    db.commit()

    return result


async def _handle_turn_inner(db: Session, witness_session: WitnessSession, latest_utterance: str) -> TurnResult:
    guard_result = await safety_guard.check_injection(latest_utterance)
    if guard_result.is_injection_attempt:
        db.add(
            EscalationEvent(
                case_id=witness_session.case_id,
                source=EscalationSource.prompt_injection_attempt,
                reason=f"matched pattern: {guard_result.matched_pattern}",
            )
        )
        return TurnResult(reply_text=safety_guard.DEFLECTION_REPLY, injection_blocked=True)

    current_params = load_current_params(db, witness_session.id)

    if witness_session.awaiting_confirmation:
        confirmed = await confirmation.classify_response(latest_utterance)
        if confirmed:
            witness_session.status = SessionStatus.confirmed_by_witness
            witness_session.awaiting_confirmation = False
            return TurnResult(
                reply_text="Thank you, this has been recorded. A caseworker will review it shortly.",
                witness_confirmed_case=True,
            )
        # Not confirmed: treat this reply as a correction and fall through
        # to the normal extraction path below, rather than wasting the turn.
        witness_session.awaiting_confirmation = False

    delta = await extraction.process_turn(latest_utterance, current_params)
    consistency_result = await consistency.check_consistency(current_params, delta)

    if consistency_result.contradictions:
        contradicting_fields = {c.field_name for c in consistency_result.contradictions}
        safe_delta = delta.model_copy()
        for field_name in contradicting_fields:
            setattr(safe_delta.updates, field_name, None)
            setattr(safe_delta.updates, f"{field_name}_verbatim", None)

        new_params = apply_delta(current_params, safe_delta)
        _persist_feature_version(db, witness_session.id, witness_session.turn_count + 1, new_params)

        # Deterministic reply for a contradiction, not LLM-generated: this
        # is a mandatory requirement (correction recovery / clarification),
        # so it must fire reliably in the live demo rather than depend on
        # the model choosing to ask about it.
        question = consistency.build_clarifying_question(consistency_result.contradictions[0])
        return TurnResult(reply_text=question)

    new_params = apply_delta(current_params, delta)
    _persist_feature_version(db, witness_session.id, witness_session.turn_count + 1, new_params)

    if new_params.is_complete_enough_for_signoff():
        witness_session.awaiting_confirmation = True
        return TurnResult(reply_text=confirmation.build_readback(new_params))

    # Same call that did extraction already composed this -- no second
    # Gemini round-trip needed for the normal (non-contradiction,
    # non-complete) path.
    return TurnResult(reply_text=delta.reply_text)
