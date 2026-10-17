from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_c3_upgrade_preserves_existing_voice_records(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / "voice.db"}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "0002")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO participants (id,data_source,created_at,consent_version) VALUES ('VOICE','public_dataset','2026-10-17','public-v1')"))
        db.execute(text("INSERT INTO voice_sessions (id,participant_id,client_session_id,request_hash,created_at,data_source,status,audio_sha256,metadata_json,result) VALUES ('voice-old','VOICE','v1','hash','2026-10-17','public_dataset','accepted','audiohash','{}','{}')"))
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM voice_sessions WHERE id='voice-old'")).scalar_one() == 1
    assert {"risk_daily", "risk_weekly", "risk_predictions"} <= set(inspect(engine).get_table_names())
    engine.dispose()
