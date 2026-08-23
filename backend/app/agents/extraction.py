"""
Feature Extraction Agent: maps the witness's free-form utterance onto the
bounded FaceParameters vocabulary, capturing the witness's own words
alongside each parsed value (the verified-vs-AI-interpretation pairing).

Fails OPEN to an empty delta -- a missed update is recoverable next turn
(the orchestrator will just ask again since the slot stays null); a
hallucinated delta would silently corrupt the case file, which is worse.
"""

from app.models.schema import FaceParameters, FeatureDelta
from app.services.gemini_client import generate_structured
from app.services.resilience import run_with_fallback

SYSTEM_PROMPT = """You extract facial-feature descriptions from a witness's spoken statement \
into a fixed vocabulary. Rules:

- Only fill in a field if the witness actually described that feature in \
this utterance. Leave everything else null -- do not guess or carry forward \
assumptions.
- For every field you fill in, also fill in the matching `_verbatim` field \
with the witness's own words for that feature (a short quote or paraphrase \
close to what they said), so the interpretation can always be checked \
against what was actually said.
- If the witness's words don't map cleanly onto any allowed value for a \
field, leave that field null rather than forcing an approximate match.
- distinguishing_marks is free text (scars, tattoos, moles) -- add new ones \
mentioned in this utterance, don't repeat ones already known."""


async def extract_delta(latest_utterance: str, current_params: FaceParameters) -> FeatureDelta:
    user_message = (
        f"Already known so far: {current_params.model_dump_json(exclude_none=True)}\n\n"
        f"Witness just said: {latest_utterance}"
    )

    async def _call() -> FeatureDelta:
        result = await generate_structured(SYSTEM_PROMPT, user_message, FaceParameters)
        return FeatureDelta(updates=result, raw_utterance=latest_utterance)

    empty_fallback = FeatureDelta(updates=FaceParameters(), raw_utterance=latest_utterance)
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
