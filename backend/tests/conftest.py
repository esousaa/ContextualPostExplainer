from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import clear_settings_cache
from app.main import app


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
