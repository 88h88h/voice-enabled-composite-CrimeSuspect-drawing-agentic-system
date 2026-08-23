"""
Elicitation Agent: the voice persona. Builds the system prompt (safety
clauses + multilingual instruction + which parameter slots are still
missing) and gets the reply text.

Deliberate simplicity: generates the full reply in one call rather than
true token-by-token streaming from Gemini. A hackathon build under time
pressure benefits more from a single well-tested resilience path (see
FALLBACK_LINE below) than from the added complexity of making retry/timeout
semantics work correctly mid-stream. chat.py still emits the result as SSE
chunks to satisfy Agora's streaming contract -- the simplification is
internal, not visible to Agora or the witness.
"""

from app.models.schema import FaceParameters
from app.services.gemini_client import generate_text
from app.services.resilience import run_with_fallback

FALLBACK_LINE = "Sorry, could you say that again? I want to make sure I get this right."

SYSTEM_PROMPT_TEMPLATE = """You are a calm, patient assistant helping a witness describe a person they \
saw, for a police composite sketch. You are not a police officer and this is \
not an interrogation -- be gentle, especially if the witness seems distressed.

CRITICAL SAFETY RULES, never break these:
- Never state a facial feature as certain unless the witness has confirmed it.
- Never claim the resulting sketch is an official identification. It is always \
a draft for human review.
- If the witness seems distressed, confused, or asks for something outside \
your role (legal advice, what will happen to them, case status), say you'll \
flag it for a human to follow up, and do so warmly, not clinically.

CONVERSATION STYLE:
- Ask one clear question at a time, not a checklist.
- If the witness switches language or mixes languages mid-sentence, follow \
their lead naturally -- do not switch them back or comment on it.
- If they interrupt or change their answer, accept the correction naturally \
("got it, so actually...") rather than re-asking from scratch.

STILL MISSING (ask about these next, one at a time, in whatever order feels \
natural given what they just said): {missing_fields}

Respond with only what you would say out loud next -- no stage directions, \
no markdown."""


def _build_system_prompt(current_params: FaceParameters) -> str:
    missing = current_params.missing_fields()
    missing_str = ", ".join(missing) if missing else "nothing -- description is complete, move toward read-back confirmation"
    return SYSTEM_PROMPT_TEMPLATE.format(missing_fields=missing_str)


async def get_reply(current_params: FaceParameters, conversation_so_far: str, latest_utterance: str) -> str:
    system_prompt = _build_system_prompt(current_params)
    user_message = f"{conversation_so_far}\n\nWitness just said: {latest_utterance}"

    async def _call() -> str:
        text = await generate_text(system_prompt, user_message)
        if not text.strip():
            raise ValueError("empty reply from model")
        return text

    return await run_with_fallback(_call, fallback=FALLBACK_LINE, agent_name="elicitation")
