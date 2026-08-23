from app.agents.reconciliation import _all_conflict_fallback, reconcile
from app.models.schema import FaceParameters, FaceShape, NoseSize, Spacing


async def test_agreement_locks_feature():
    a = FaceParameters(eyes_spacing=Spacing.close_set, eyes_spacing_verbatim="close together")
    b = FaceParameters(eyes_spacing=Spacing.close_set, eyes_spacing_verbatim="near each other")
    result = await reconcile(a, b)
    assert result.reconciled.eyes_spacing == Spacing.close_set
    assert result.conflicts == []


async def test_single_source_carries_forward_without_conflict():
    a = FaceParameters(nose_size=NoseSize.small, nose_size_verbatim="small nose")
    b = FaceParameters(face_shape=FaceShape.oval, face_shape_verbatim="oval face")
    result = await reconcile(a, b)
    assert result.reconciled.nose_size == NoseSize.small
    assert result.reconciled.face_shape == FaceShape.oval
    assert result.conflicts == []


async def test_real_disagreement_flagged_not_silently_merged():
    a = FaceParameters(nose_size=NoseSize.small, nose_size_verbatim="small nose")
    b = FaceParameters(nose_size=NoseSize.large, nose_size_verbatim="big nose")
    result = await reconcile(a, b)
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.field_name == "nose_size"
    assert conflict.witness_a_value == "small"
    assert conflict.witness_b_value == "large"
    assert result.reconciled.nose_size is None


async def test_distinguishing_marks_union_deduped():
    a = FaceParameters(distinguishing_marks=["scar on chin"])
    b = FaceParameters(distinguishing_marks=["scar on chin", "mole on cheek"])
    result = await reconcile(a, b)
    assert set(result.reconciled.distinguishing_marks) == {"scar on chin", "mole on cheek"}


def test_fail_closed_fallback_flags_every_filled_field_as_conflict():
    a = FaceParameters(nose_size=NoseSize.small, nose_size_verbatim="small")
    b = FaceParameters(face_shape=FaceShape.oval, face_shape_verbatim="oval")
    fb = _all_conflict_fallback(a, b)
    assert len(fb.conflicts) == 2
    assert fb.reconciled.model_dump(exclude_none=True) == {"distinguishing_marks": []}
