"""
Confirmation Agent: the live read-back step required before a case is filed
-- distinct from, and prior to, the downstream human caseworker sign-off.
Builds the read-back text (interpretation + the witness's own verbatim
words, side by side -- same verified/AI-interpreted pairing as everywhere
else) and classifies whether the witness's reply actually confirms it.

Classification fails toward "not yet confirmed" on any failure -- same
fail-closed reasoning as Reconciliation/Escalation: this is a gate before
filing a case, so an ambiguous or failed read is never treated as a yes.
"""

from pydantic import BaseModel

from app.models.schema import FaceParameters
from app.services.gemini_client import generate_structured
from app.services.resilience import run_with_fallback

_FIELD_LABELS = {
    "face_shape": "face shape",
    "eyes_shape": "eye shape",
    "eyes_spacing": "eye spacing",
    "eyebrows_thickness": "eyebrow thickness",
    "nose_size": "nose size",
    "nose_shape": "nose shape",
    "mouth_width": "mouth width",
    "jaw_shape": "jaw shape",
    "hair_length": "hair length",
    "hair_texture": "hair texture",
    "hair_color": "hair color",
    "facial_hair": "facial hair",
}


def build_readback(params: FaceParameters) -> str:
    parts = []
    for field_name, label in _FIELD_LABELS.items():
        value = getattr(params, field_name)
        if value is not None:
            value_str = value.value if hasattr(value, "value") else str(value)
            parts.append(f"{label}: {value_str}")
    if params.distinguishing_marks:
        parts.append("distinguishing marks: " + ", ".join(params.distinguishing_marks))

    if not parts:
        return "I don't have enough details yet to read anything back to you."

    listed = "; ".join(parts)
    return f"So to confirm what I have so far: {listed}. Is that all correct?"


class ConfirmationClassification(BaseModel):
    witness_confirmed: bool


async def classify_response(witness_reply: str) -> bool:
    system_prompt = (
        "The witness was just read back a description and asked if it's correct. "
        "Classify their reply as confirming (true) only if they clearly agree with "
        "no corrections -- in any language or mixed languages. If they correct "
        "anything, express doubt, or don't clearly confirm, return false."
    )

    async def _call() -> bool:
        result = await generate_structured(system_prompt, witness_reply, ConfirmationClassification)
        return result.witness_confirmed

    # Fails toward False (not yet confirmed) -- a case should never be filed
    # off the back of a failed classification.
    return await run_with_fallback(_call, fallback=False, agent_name="confirmation", timeout_s=6.0, retries=1)
