from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from app.database import Base
import app.models  # noqa: F401


def test_c4_upgrade_preserves_existing_longitudinal_data(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / "old-c3.db"}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "0003")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO participants (id,data_source,created_at,consent_version) VALUES ('OLD','synthetic_demo','2026-10-17T00:00:00Z','demo-v1')"))
        db.execute(text("INSERT INTO risk_daily (id,participant_id,client_record_id,request_hash,data_source,observed_on,reported_at,ingested_at,payload) VALUES ('old-daily','OLD','d1','h','synthetic_demo','2026-10-16','2026-10-16T12:00:00Z','2026-10-17T00:00:00Z','{}')"))
        db.execute(text("INSERT INTO risk_predictions (id,participant_id,client_prediction_id,request_hash,created_at,as_of,data_source,status,snapshot_hash,result) VALUES ('old-risk','OLD','p1','h','2026-10-17T01:00:00Z','2026-10-17T01:00:00Z','synthetic_demo','insufficient_history','h','{}')"))
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005"
        assert db.execute(text("SELECT COUNT(*) FROM risk_daily WHERE id='old-daily'")).scalar_one() == 1
        assert db.execute(text("SELECT COUNT(*) FROM risk_predictions WHERE id='old-risk'")).scalar_one() == 1
    schema = inspect(engine)
    for name, table in Base.metadata.tables.items():
        assert {column.name for column in table.columns} == {column["name"] for column in schema.get_columns(name)}
    engine.dispose()
