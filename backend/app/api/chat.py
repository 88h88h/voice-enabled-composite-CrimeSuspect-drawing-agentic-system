"""
POST /chat/completions: the endpoint Agora's Conversational AI Engine calls
for the reasoning step of every turn. Must look and stream like the OpenAI
Chat Completions API (see plan) -- everything agent-specific happens inside
orchestrator.handle_turn(); this file only translates between Agora's
request/response shape and our own.

Every call is treated as stateless: we never trust Agora to have replayed
full history, we pull the witness's session and locked parameters from our
own DB by session_id and reconstruct from there.
"""

import time
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session, select

from app.agents import composite_generation, orchestrator
from app.database import get_session
from app.models.db import SketchImage, SketchStatus, WitnessSession
from app.services.image_store import load_sketch, save_sketch

router = APIRouter()


def _latest_user_message(body: dict) -> str:
    messages = body.get("messages", [])
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, list):  # some OpenAI-compatible clients send content as parts
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return content
    raise HTTPException(status_code=400, detail="no user message found in request body")


def _sse_chunk(reply_text: str, model: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {"content": reply_text}, "finish_reason": None}],
    }


def _sse_final_chunk(model: str) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }


async def generate_and_save_sketch(db: Session, case_id: str, session_id: str) -> None:
    """Core logic, DB-injected for testability (same pattern as
    orchestrator.handle_turn). Skips the external call entirely when the
    parameters haven't changed since the last successful generation -- this
    is a real-money API call, not just a UX nicety to debounce."""
    params = orchestrator.load_current_params(db, session_id)
    if not params.filled_fields():
        return

    previous = db.exec(
        select(SketchImage)
        .where(SketchImage.session_id == session_id, SketchImage.status == SketchStatus.ready)
        .order_by(SketchImage.created_at.desc())
    ).first()

    current_params_json = params.model_dump_json()
    if previous is not None and previous.parameters_json == current_params_json:
        # Nothing changed since the last successful generation. A prior
        # FAILED attempt does NOT block a retry here, only a matching
        # READY one does.
        return

    previous_bytes = load_sketch(previous.file_path) if previous else None

    image_bytes = await composite_generation.generate_composite(params, previous_bytes)

    if image_bytes is None:
        db.add(
            SketchImage(
                case_id=case_id,
                session_id=session_id,
                status=SketchStatus.generation_failed,
                parameters_json=current_params_json,
            )
        )
    else:
        file_path, _ = save_sketch(image_bytes)
        db.add(
            SketchImage(
                case_id=case_id,
                session_id=session_id,
                file_path=file_path,
                status=SketchStatus.ready,
                parameters_json=current_params_json,
            )
        )
    db.commit()


async def _generate_and_save_sketch(case_id: str, session_id: str) -> None:
    """Runs after the turn's SSE response has already been sent -- the
    external action (composite generation) never blocks the live
    conversational reply. Thin wrapper: opens its own DB session since the
    request-scoped one may already be closed by the time this fires."""
    with get_session() as db:
        await generate_and_save_sketch(db, case_id, session_id)


@router.post("/chat/completions")
async def chat_completions(request: Request, background_tasks: BackgroundTasks):
    session_id = request.query_params.get("session_id")
    case_id = request.query_params.get("case_id")
    if not session_id or not case_id:
        raise HTTPException(status_code=400, detail="session_id and case_id query params are required")

    body = await request.json()
    model = body.get("model", "witness-agent")
    latest_utterance = _latest_user_message(body)

    with get_session() as db:
        witness_session = db.get(WitnessSession, session_id)
        if witness_session is None:
            raise HTTPException(status_code=404, detail=f"unknown session_id {session_id!r}")

        result = await orchestrator.handle_turn(db, witness_session, latest_utterance)

    if not result.injection_blocked:
        background_tasks.add_task(_generate_and_save_sketch, case_id, session_id)

    async def event_stream():
        yield {"data": _json(_sse_chunk(result.reply_text, model))}
        yield {"data": _json(_sse_final_chunk(model))}
        yield {"data": "[DONE]"}

    return EventSourceResponse(event_stream())


def _json(payload) -> str:
    import json

    return json.dumps(payload)
