from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from jlpt_studio.core.config import get_settings
from jlpt_studio.db.base import Base
from jlpt_studio.db.session import get_engine, reset_db_for_tests


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch) -> Generator[None, None, None]:
    monkeypatch.setenv("JLPT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JLPT_DATABASE_URL", f"sqlite:///{tmp_path / 'test.sqlite3'}")
    get_settings.cache_clear()
    reset_db_for_tests()
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())
    reset_db_for_tests()
    get_settings.cache_clear()


@pytest.fixture()
def client(isolated_db) -> Generator[TestClient, None, None]:
    from jlpt_studio.main import app

    with TestClient(app) as test_client:
        yield test_client

