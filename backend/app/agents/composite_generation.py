"""
Composite Generation Agent: the mandatory external action. Builds a prompt
from the full LOCKED parameter set (never just the latest delta) so an edit
only changes what actually changed -- passing the full canonical
description each time is what keeps Gemini 2.5 Flash Image's iterative
edits from drifting turn over turn, verified by the 5-chained-edit test
below.

Fails after one retry to a None result -- caller marks the sketch
GENERATION_FAILED and keeps the last good image; this never blocks the
live conversational turn because callers run it as a background task.
"""

from app.models.schema import FaceParameters
from app.services.gemini_client import generate_image
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


def build_image_prompt(params: FaceParameters, is_edit: bool) -> str:
    descriptors = []
    for field_name, label in _FIELD_LABELS.items():
        value = getattr(params, field_name)
        if value is not None:
            value_str = value.value if hasattr(value, "value") else str(value)
            descriptors.append(f"{label}: {value_str}")
    if params.distinguishing_marks:
        descriptors.append("distinguishing marks: " + ", ".join(params.distinguishing_marks))

    description = "; ".join(descriptors) if descriptors else "no distinctive features described yet"

    base = (
        "Black-and-white forensic composite sketch style, front-facing, neutral "
        "expression, plain background. This is a DRAFT investigative sketch, not "
        "a photograph. "
        f"Facial description: {description}."
    )
    if is_edit:
        return base + " Keep every other feature of the existing sketch identical; only adjust the feature(s) that changed."
    return base


async def generate_composite(params: FaceParameters, previous_image_bytes: bytes | None) -> bytes | None:
    prompt = build_image_prompt(params, is_edit=previous_image_bytes is not None)

    async def _call() -> bytes:
        return await generate_image(prompt, reference_image_bytes=previous_image_bytes)

    return await run_with_fallback(
        _call, fallback=None, agent_name="composite_generation", timeout_s=25.0, retries=1
    )
