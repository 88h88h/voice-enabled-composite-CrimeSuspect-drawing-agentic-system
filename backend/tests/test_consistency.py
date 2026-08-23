from app.agents.consistency import build_clarifying_question, check_consistency
from app.agents.extraction import apply_delta
from app.models.schema import FaceParameters, FeatureDelta, Spacing


async def test_detects_real_contradiction():
    locked = FaceParameters(eyes_spacing=Spacing.close_set, eyes_spacing_verbatim="eyes close together")
    delta = FeatureDelta(
        updates=FaceParameters(eyes_spacing=Spacing.wide_set, eyes_spacing_verbatim="wide apart eyes"),
        raw_utterance="actually wide apart",
    )
    result = await check_consistency(locked, delta)
    assert len(result.contradictions) == 1
    c = result.contradictions[0]
    assert c.field_name == "eyes_spacing"
    assert c.previous_value == "close-set"
    assert c.new_value == "wide-set"


async def test_no_false_positive_on_new_field():
    locked = FaceParameters(eyes_spacing=Spacing.close_set, eyes_spacing_verbatim="close")
    delta = FeatureDelta(
        updates=FaceParameters(nose_size="small", nose_size_verbatim="small nose"), raw_utterance="small nose"
    )
    result = await check_consistency(locked, delta)
    assert result.contradictions == []


async def test_clarifying_question_uses_verbatim_quotes():
    locked = FaceParameters(eyes_spacing=Spacing.close_set, eyes_spacing_verbatim="eyes close together")
    delta = FeatureDelta(
        updates=FaceParameters(eyes_spacing=Spacing.wide_set, eyes_spacing_verbatim="wide apart eyes"),
        raw_utterance="x",
    )
    result = await check_consistency(locked, delta)
    question = build_clarifying_question(result.contradictions[0])
    assert "eyes close together" in question
    assert "wide apart eyes" in question


def test_apply_delta_overwrites_only_filled_fields():
    locked = FaceParameters(eyes_spacing=Spacing.close_set, eyes_spacing_verbatim="close")
    delta = FeatureDelta(
        updates=FaceParameters(eyes_spacing=Spacing.wide_set, eyes_spacing_verbatim="wide"), raw_utterance="x"
    )
    merged = apply_delta(locked, delta)
    assert merged.eyes_spacing == Spacing.wide_set
