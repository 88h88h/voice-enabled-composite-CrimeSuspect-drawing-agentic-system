"""
Safety Guard: fast, deterministic prompt-injection/jailbreak check on
witness input, run before anything else touches an utterance. Pattern-based
by design, not an LLM call -- zero added latency in the live voice turn,
and its behavior is fully deterministic and testable, which matters more
here than catching every possible phrasing.

Fails CLOSED: if the check itself throws (malformed input, unexpected
type), treat it as a detected injection attempt rather than silently
passing the utterance through. Same reasoning as Reconciliation/Escalation:
a safety gate that fails open is not a safety gate.
"""

import re

from pydantic import BaseModel

from app.services.resilience import run_with_fallback

_INJECTION_PATTERNS = [
    r"ignore (all |the )?(previous|prior|above) instructions",
    r"disregard (all |the )?(previous|prior|above)",
    r"you are now\b",
    r"new instructions\s*:",
    r"system\s*:",
    r"reveal (your|the) (system )?prompt",
    r"print (your|the) instructions",
    r"act as\b.*\b(dan|jailbreak|unrestricted)",
    r"pretend (you are|to be) (an? )?(unfiltered|uncensored)",
    r"forget (you are|your) (rules|guidelines|instructions)",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


class GuardResult(BaseModel):
    is_injection_attempt: bool
    matched_pattern: str | None = None


DEFLECTION_REPLY = (
    "I can only help with describing what you saw for this case. "
    "Let's continue with that -- could you tell me more about the person's appearance?"
)


async def check_injection(utterance: str) -> GuardResult:
    async def _call() -> GuardResult:
        for pattern in _COMPILED:
            match = pattern.search(utterance)
            if match:
                return GuardResult(is_injection_attempt=True, matched_pattern=match.group(0))
        return GuardResult(is_injection_attempt=False)

    fail_closed_fallback = GuardResult(is_injection_attempt=True, matched_pattern="<guard check itself failed>")
    return await run_with_fallback(_call, fallback=fail_closed_fallback, agent_name="safety_guard", timeout_s=1.0, retries=0)
