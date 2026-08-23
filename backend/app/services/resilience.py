"""
Shared per-agent resilience wrapper. Every agent call goes through
run_with_fallback rather than a raw try/except, so the retry/timeout/logging
policy is consistent and each agent only has to state ONE thing: its
fallback value, chosen deliberately for its own stakes (see agents/*.py
docstrings). Fail-open agents return a safe "do nothing new" fallback;
fail-closed agents (reconciliation, escalation classification) return a
fallback that routes to a human rather than guessing.

Also transparently records per-call latency via a contextvar-based trace
collector (see trace_session() below), so agent modules don't need to know
anything about tracing -- orchestrator.py opens a trace_session() around a
turn, and every run_with_fallback call inside it is recorded automatically.
This exists specifically to answer "what's your actual latency breakdown"
with real numbers instead of a claim.
"""

import asyncio
import contextvars
import logging
import time
from contextlib import contextmanager
from typing import Awaitable, Callable, Iterator, TypeVar

from pydantic import BaseModel

logger = logging.getLogger("resilience")

T = TypeVar("T")


class TraceRecord(BaseModel):
    agent_name: str
    duration_ms: float
    used_fallback: bool
    attempts: int


_trace_collector: contextvars.ContextVar[list[TraceRecord] | None] = contextvars.ContextVar(
    "trace_collector", default=None
)


@contextmanager
def trace_session() -> Iterator[list[TraceRecord]]:
    """Open around one conversational turn. Every run_with_fallback call
    made anywhere during the `with` block appends a TraceRecord to the
    yielded list -- orchestrator.py persists it to TurnTrace rows on exit."""
    records: list[TraceRecord] = []
    token = _trace_collector.set(records)
    try:
        yield records
    finally:
        _trace_collector.reset(token)


async def run_with_fallback(
    func: Callable[[], Awaitable[T]],
    *,
    fallback: T,
    agent_name: str,
    timeout_s: float = 8.0,
    retries: int = 1,
) -> T:
    start = time.monotonic()
    last_error: Exception | None = None
    attempts_made = 0

    for attempt in range(retries + 1):
        attempts_made = attempt + 1
        try:
            result = await asyncio.wait_for(func(), timeout=timeout_s)
            _record_trace(agent_name, start, used_fallback=False, attempts=attempts_made)
            return result
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any failure of any agent must fall back, not crash the turn
            last_error = exc
            logger.warning(
                "agent=%s attempt=%d/%d failed: %s",
                agent_name,
                attempt + 1,
                retries + 1,
                exc,
            )

    logger.error("agent=%s exhausted retries, using fallback. last_error=%s", agent_name, last_error)
    _record_trace(agent_name, start, used_fallback=True, attempts=attempts_made)
    return fallback


def _record_trace(agent_name: str, start: float, *, used_fallback: bool, attempts: int) -> None:
    collector = _trace_collector.get()
    if collector is None:
        return
    duration_ms = (time.monotonic() - start) * 1000
    collector.append(
        TraceRecord(agent_name=agent_name, duration_ms=round(duration_ms, 1), used_fallback=used_fallback, attempts=attempts)
    )
