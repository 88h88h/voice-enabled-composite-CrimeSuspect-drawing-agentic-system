from app.agents.confirmation import build_readback
from app.models.schema import FaceParameters, FaceShape


def test_readback_lists_locked_features_and_asks_to_confirm():
    p = FaceParameters(face_shape=FaceShape.oval, face_shape_verbatim="oval-ish")
    rb = build_readback(p)
    assert "face shape: oval" in rb
    assert rb.endswith("correct?")


def test_readback_on_empty_params():
    rb = build_readback(FaceParameters())
    assert "enough details" in rb


def test_readback_includes_distinguishing_marks():
    p = FaceParameters(distinguishing_marks=["scar on chin", "mole on cheek"])
    rb = build_readback(p)
    assert "scar on chin" in rb and "mole on cheek" in rb
