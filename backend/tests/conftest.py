import os

os.environ.setdefault("GEMINI_API_KEY", "dummy-for-tests")

import pytest
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
