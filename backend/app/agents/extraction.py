"""
Combined Extraction + Elicitation Agent: one Gemini call that both maps the
witness's utterance onto the bounded FaceParameters vocabulary AND composes
the natural-language reply, instead of two sequential calls.

Merged deliberately for latency: measured via our own TurnTrace data,
separate extraction (~4-6s) + elicitation (~4.5-7s) calls cost 9-13s per
turn, sequentially -- exactly the kind of round-trip a live voice demo
can't survive. One combined call cuts that to a single round-trip. The
orchestrator still overrides reply_text deterministically for contradictions
and completion read-backs (see orchestrator.py), so this changes latency
only, not any correctness/safety guarantee.

Fails OPEN to an empty delta and a scripted fallback line -- a missed
update is recoverable next turn (the slot stays null, gets asked again); a
hallucinated delta would silently corrupt the case file, which is worse.
"""

from app.models.schema import ExtractedTurn, FaceParameters, FeatureDelta
from app.services.gemini_client import generate_structured
from app.services.resilience import run_with_fallback

FALLBACK_LINE = "Sorry, could you say that again? I want to make sure I get this right."

SYSTEM_PROMPT = """You are a calm, patient assistant helping a witness describe a person they \
saw, for a police composite sketch. You are not a police officer and this is \
not an interrogation -- be gentle, especially if the witness seems distressed.

You do TWO things at once for every witness utterance:

1. EXTRACT facial features into a fixed vocabulary (the `updates` field):
   - Only fill in a field if the witness actually described that feature in \
this utterance. Leave everything else null -- do not guess or carry forward \
assumptions.
   - For every field you fill in, also fill in the matching `_verbatim` field \
with the witness's own words for that feature (a short quote or paraphrase \
close to what they said).
   - If the witness's words don't map cleanly onto any allowed value for a \
field, leave that field null rather than forcing an approximate match.
   - distinguishing_marks is free text (scars, tattoos, moles) -- add new \
ones mentioned in this utterance, don't repeat ones already known.

2. COMPOSE a natural spoken reply (the `reply_text` field):
   - Ask one clear question at a time, not a checklist.
   - If the witness switches language or mixes languages mid-sentence, follow \
their lead naturally -- do not switch them back or comment on it.
   - If they interrupt or change their answer, accept the correction naturally \
("got it, so actually...") rather than re-asking from scratch.
   - Never state a facial feature as certain unless the witness has confirmed it.
   - Never claim the resulting sketch is an official identification. It is \
always a draft for human review.
   - If the witness seems distressed, confused, or asks for something outside \
your role (legal advice, what will happen to them, case status), say you'll \
flag it for a human to follow up, and do so warmly, not clinically.
   - Respond with only what you would say out loud next -- no stage \
directions, no markdown.
   - Keep it short: one sentence acknowledging what they said (if anything \
new), then one short question. Real spoken conversation is brief, not a \
paragraph -- and a shorter reply is also faster for you to generate and \
faster for the witness to hear.

STILL MISSING (ask about these next, one at a time, in whatever order feels \
natural given what they just said): {missing_fields}"""


def _build_system_prompt(current_params: FaceParameters) -> str:
    missing = current_params.missing_fields()
    missing_str = ", ".join(missing) if missing else "nothing -- description is complete, move toward read-back confirmation"
    return SYSTEM_PROMPT.format(missing_fields=missing_str)


async def process_turn(latest_utterance: str, current_params: FaceParameters) -> FeatureDelta:
    system_prompt = _build_system_prompt(current_params)
    user_message = (
        f"Already known so far: {current_params.model_dump_json(exclude_none=True)}\n\n"
        f"Witness just said: {latest_utterance}"
    )

    async def _call() -> FeatureDelta:
        result = await generate_structured(system_prompt, user_message, ExtractedTurn)
        if not result.reply_text.strip():
            raise ValueError("empty reply_text from model")
        return FeatureDelta(updates=result.updates, raw_utterance=latest_utterance, reply_text=result.reply_text)

    empty_fallback = FeatureDelta(updates=FaceParameters(), raw_utterance=latest_utterance, reply_text=FALLBACK_LINE)
    return await run_with_fallback(_call, fallback=empty_fallback, agent_name="extraction")


def apply_delta(current: FaceParameters, delta: FeatureDelta) -> FaceParameters:
    """Merge: only overwrite fields the delta actually filled in."""
    merged = current.model_copy()
    for field_name in delta.updates.filled_fields():
        setattr(merged, field_name, getattr(delta.updates, field_name))
        verbatim_field = f"{field_name}_verbatim"
        setattr(merged, verbatim_field, getattr(delta.updates, verbatim_field))
    if delta.updates.distinguishing_marks:
        merged.distinguishing_marks = list(
            dict.fromkeys(merged.distinguishing_marks + delta.updates.distinguishing_marks)
        )
    return merged
