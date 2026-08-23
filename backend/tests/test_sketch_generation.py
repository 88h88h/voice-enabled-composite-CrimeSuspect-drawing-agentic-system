"""
Covers the cost-safety behavior: composite generation (a real-money external
call) must be skipped when parameters haven't changed since the last
successful generation, but must still retry if the last attempt failed.
"""

from unittest.mock import AsyncMock

from app.api.chat import generate_and_save_sketch
from app.models.db import Case, SketchStatus, WitnessSession
from app.models.schema import FaceParameters


def _seed(db):
    case = Case(incident_location="x")
    db.add(case)
    db.commit()
    db.refresh(case)
    session = WitnessSession(case_id=case.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return case, session


def _seed_feature_version(db, session_id, params: FaceParameters):
    from app.models.db import FeatureVersion

    db.add(FeatureVersion(session_id=session_id, turn_index=1, parameters_json=params.model_dump_json()))
    db.commit()


async def test_skips_when_no_fields_filled(db_session, monkeypatch):
    case, session = _seed(db_session)
    generate_mock = AsyncMock(return_value=b"fake-image-bytes")
    monkeypatch.setattr("app.api.chat.composite_generation.generate_composite", generate_mock)

    await generate_and_save_sketch(db_session, case.id, session.id)

    generate_mock.assert_not_called()


async def test_generates_on_first_call_with_filled_params(db_session, monkeypatch, tmp_path):
    case, session = _seed(db_session)
    _seed_feature_version(db_session, session.id, FaceParameters(face_shape="oval", face_shape_verbatim="a"))

    generate_mock = AsyncMock(return_value=b"fake-image-bytes")
    monkeypatch.setattr("app.api.chat.composite_generation.generate_composite", generate_mock)
    monkeypatch.setattr("app.api.chat.save_sketch", lambda b: (str(tmp_path / "x.png"), "http://x/x.png"))

    await generate_and_save_sketch(db_session, case.id, session.id)

    generate_mock.assert_called_once()


async def test_skips_when_params_unchanged_since_last_ready_sketch(db_session, monkeypatch, tmp_path):
    case, session = _seed(db_session)
    params = FaceParameters(face_shape="oval", face_shape_verbatim="a")
    _seed_feature_version(db_session, session.id, params)

    from app.models.db import SketchImage

    db_session.add(
        SketchImage(
            case_id=case.id,
            session_id=session.id,
            file_path=str(tmp_path / "existing.png"),
            status=SketchStatus.ready,
            parameters_json=params.model_dump_json(),
        )
    )
    (tmp_path / "existing.png").write_bytes(b"prior-image")
    db_session.commit()

    generate_mock = AsyncMock(return_value=b"new-image-bytes")
    monkeypatch.setattr("app.api.chat.composite_generation.generate_composite", generate_mock)

    await generate_and_save_sketch(db_session, case.id, session.id)

    generate_mock.assert_not_called()


async def test_regenerates_when_params_changed(db_session, monkeypatch, tmp_path):
    case, session = _seed(db_session)
    old_params = FaceParameters(face_shape="oval", face_shape_verbatim="a")
    new_params = FaceParameters(face_shape="round", face_shape_verbatim="round now")
    _seed_feature_version(db_session, session.id, new_params)

    from app.models.db import SketchImage

    db_session.add(
        SketchImage(
            case_id=case.id,
            session_id=session.id,
            file_path=str(tmp_path / "existing.png"),
            status=SketchStatus.ready,
            parameters_json=old_params.model_dump_json(),
        )
    )
    (tmp_path / "existing.png").write_bytes(b"prior-image")
    db_session.commit()

    generate_mock = AsyncMock(return_value=b"new-image-bytes")
    monkeypatch.setattr("app.api.chat.composite_generation.generate_composite", generate_mock)
    monkeypatch.setattr("app.api.chat.save_sketch", lambda b: (str(tmp_path / "new.png"), "http://x/new.png"))

    await generate_and_save_sketch(db_session, case.id, session.id)

    generate_mock.assert_called_once()
    # confirms the PREVIOUS image bytes were passed through for iterative editing
    assert generate_mock.call_args.args[1] == b"prior-image"


async def test_retries_after_a_prior_failed_attempt_with_same_params(db_session, monkeypatch, tmp_path):
    case, session = _seed(db_session)
    params = FaceParameters(face_shape="oval", face_shape_verbatim="a")
    _seed_feature_version(db_session, session.id, params)

    from app.models.db import SketchImage

    db_session.add(
        SketchImage(
            case_id=case.id,
            session_id=session.id,
            status=SketchStatus.generation_failed,
            parameters_json=params.model_dump_json(),
        )
    )
    db_session.commit()

    generate_mock = AsyncMock(return_value=b"recovered-image-bytes")
    monkeypatch.setattr("app.api.chat.composite_generation.generate_composite", generate_mock)
    monkeypatch.setattr("app.api.chat.save_sketch", lambda b: (str(tmp_path / "new.png"), "http://x/new.png"))

    await generate_and_save_sketch(db_session, case.id, session.id)

    generate_mock.assert_called_once()
