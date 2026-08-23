"""
Shared per-agent resilience wrapper. Every agent call goes through
run_with_fallback rather than a raw try/except, so the retry/timeout/logging
policy is consistent and each agent only has to state ONE thing: its
fallback value, chosen deliberately for its own stakes (see agents/*.py
docstrings). Fail-open agents return a safe "do nothing new" fallback;
fail-closed agents (reconciliation, escalation classification) return a
fallback that routes to a human rather than guessing.
"""

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger("resilience")

T = TypeVar("T")


async def run_with_fallback(
    func: Callable[[], Awaitable[T]],
    *,
    fallback: T,
    agent_name: str,
    timeout_s: float = 8.0,
    retries: int = 1,
) -> T:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(func(), timeout=timeout_s)
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
    return fallback
