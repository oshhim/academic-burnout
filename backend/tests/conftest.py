from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / "test.db"}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")
    settings = Settings(database_url=url, api_key="unit-test-key-123456", enable_research_mode=False)
    with TestClient(create_app(settings)) as http:
        http.headers["X-API-Key"] = settings.api_key
        yield http

