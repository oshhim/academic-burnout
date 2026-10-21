from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from pathlib import Path


def test_upgrade_from_c1_preserves_participants_and_facial_records(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / "old.db"}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "0001")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO participants (id,data_source,created_at,consent_version) VALUES ('EXISTING','synthetic_demo','2026-10-11T10:00:00+00:00','demo-v1')"))
        db.execute(text("INSERT INTO facial_sessions (id,participant_id,client_session_id,request_hash,recorded_at,created_at,kind,data_source,status,features,result) VALUES ('old-session','EXISTING','old','hash','2026-10-11','2026-10-11','calibration','synthetic_demo','accepted','{}','{}')"))
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM participants WHERE id='EXISTING'")).scalar_one() == 1
        assert db.execute(text("SELECT COUNT(*) FROM facial_sessions WHERE id='old-session'")).scalar_one() == 1
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005"
    assert "voice_sessions" in inspect(engine).get_table_names()
    engine.dispose()
