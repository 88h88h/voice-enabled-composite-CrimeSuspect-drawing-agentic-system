from app.agents.composite_generation import build_image_prompt
from app.models.schema import FaceParameters, FaceShape, NoseSize


def test_prompt_includes_locked_features_and_marks():
    p = FaceParameters(
        face_shape=FaceShape.oval,
        face_shape_verbatim="oval-ish",
        nose_size=NoseSize.small,
        nose_size_verbatim="small",
        distinguishing_marks=["scar on chin"],
    )
    prompt = build_image_prompt(p, is_edit=False)
    assert "face shape: oval" in prompt
    assert "scar on chin" in prompt
    assert "Keep every other feature" not in prompt


def test_edit_prompt_asks_to_preserve_other_features():
    p = FaceParameters(face_shape=FaceShape.oval, face_shape_verbatim="oval")
    prompt = build_image_prompt(p, is_edit=True)
    assert "Keep every other feature" in prompt


def test_empty_params_still_produces_valid_prompt():
    prompt = build_image_prompt(FaceParameters(), is_edit=False)
    assert "no distinctive features" in prompt
