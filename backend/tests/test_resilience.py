import asyncio

import pytest

from app.services.resilience import run_with_fallback, trace_session


async def test_success_case():
    async def ok():
        return "real result"

    assert await run_with_fallback(ok, fallback="FB", agent_name="t") == "real result"


async def test_exhausts_retries_then_falls_back():
    attempts = []

    async def always_fails():
        attempts.append(1)
        raise ValueError("boom")

    result = await run_with_fallback(always_fails, fallback="FB", agent_name="t", retries=2, timeout_s=1)
    assert result == "FB"
    assert len(attempts) == 3


async def test_timeout_falls_back():
    async def hangs():
        await asyncio.sleep(5)

    result = await run_with_fallback(hangs, fallback="TIMEOUT_FB", agent_name="t", retries=0, timeout_s=0.2)
    assert result == "TIMEOUT_FB"


async def test_recovers_after_transient_failure():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("flake")
        return "recovered"

    result = await run_with_fallback(flaky, fallback="FB", agent_name="t", retries=2, timeout_s=1)
    assert result == "recovered"


async def test_trace_session_captures_calls():
    async def ok():
        return "x"

    async def fails():
        raise ValueError("x")

    with trace_session() as traces:
        await run_with_fallback(ok, fallback="FB", agent_name="agentA", retries=0)
        await run_with_fallback(fails, fallback="FB", agent_name="agentB", retries=1, timeout_s=1)

    assert len(traces) == 2
    assert traces[0].agent_name == "agentA" and traces[0].used_fallback is False
    assert traces[1].agent_name == "agentB" and traces[1].used_fallback is True and traces[1].attempts == 2


async def test_works_fine_outside_trace_session():
    async def ok():
        return "x"

    assert await run_with_fallback(ok, fallback="FB", agent_name="agentC", retries=0) == "x"
