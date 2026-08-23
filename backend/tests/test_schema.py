from app.models.schema import FaceParameters, FaceShape


def test_filled_and_missing_fields():
    fp = FaceParameters(face_shape=FaceShape.oval, face_shape_verbatim="oval-ish")
    assert fp.filled_fields() == ["face_shape"]
    assert "face_shape" not in fp.missing_fields()
    assert len(fp.missing_fields()) == 11


def test_signoff_readiness_threshold():
    fp = FaceParameters(face_shape=FaceShape.oval, face_shape_verbatim="oval")
    assert fp.is_complete_enough_for_signoff() is False

    for i, field in enumerate(
        ["eyes_shape", "eyes_spacing", "eyebrows_thickness", "nose_size", "nose_shape", "mouth_width", "jaw_shape"]
    ):
        pass  # just checking count-based logic below, not exhaustively filling every enum type

    filled = FaceParameters(
        face_shape=FaceShape.oval,
        face_shape_verbatim="a",
        eyes_shape="almond",
        eyes_shape_verbatim="a",
        eyes_spacing="average",
        eyes_spacing_verbatim="a",
        eyebrows_thickness="medium",
        eyebrows_thickness_verbatim="a",
        nose_size="small",
        nose_size_verbatim="a",
        nose_shape="straight",
        nose_shape_verbatim="a",
        mouth_width="medium",
        mouth_width_verbatim="a",
        jaw_shape="round",
        jaw_shape_verbatim="a",
    )
    assert filled.is_complete_enough_for_signoff() is True
