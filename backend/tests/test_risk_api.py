import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.risk.features import parse_time, snapshot
from app.risk.model import RiskModel
from scripts.risk_demo_data import demo_observations
from scripts.run_risk_demo import run_risk_demo

ROOT = Path(__file__).resolve().parents[1]


def populate(client, pid="R1", profile="steady", source="synthetic_demo", limited=False):
    response = client.post("/api/v1/participants", json={"participant_id": pid, "data_source": source, "consent": True})
    assert response.status_code == 201, response.text
    daily, weekly = demo_observations(pid, profile, source)
    response = client.post("/api/v1/risk/daily/batch", json={"records": daily[-7:] if limited else daily})
    assert response.status_code == 201, response.text
    for row in weekly:
        assert client.post("/api/v1/risk/weekly", json=row).status_code == 201
    return daily, weekly


def evaluate(client, pid="R1", prediction_id="p1", **extra):
    return client.post("/api/v1/risk/predictions", json={"participant_id": pid, "client_prediction_id": prediction_id, **extra})


def test_live_demo_profiles_and_synthetic_evidence(client):
    result = run_risk_demo(client)["scenarios"]
    assert result["steady"]["status"] == "demo_only_prediction"
    assert result["rising"]["status"] == "demo_only_prediction"
    assert result["missing_weekly"]["snapshot"]["features"]["weekly_missing"] == 1
    assert result["sparse"]["status"] == "insufficient_history" and result["sparse"]["risk"] is None
    assert result["steady"]["risk"]["clinical_risk_probability"] is None
    assert result["steady"]["evidence"]["training_data_source"] == "synthetic_demo"
    assert result["steady"]["evidence"]["model_applied"] is True
    assert result["steady"]["snapshot"]["modality_context"]["facial_or_voice_used_as_risk_predictors"] is False


def test_ingestion_retries_immutability_and_server_time(client):
    daily, _ = populate(client)
    one = client.post("/api/v1/risk/daily", json=daily[0])
    two = client.post("/api/v1/risk/daily", json=daily[0])
    assert one.json() == two.json()
    assert "ingested_at" in one.json()
    assert client.post("/api/v1/risk/daily", json={**daily[0], "sleep_hours": 4}).status_code == 409
    assert client.post("/api/v1/risk/daily", json={**daily[0], "ingested_at": "2025-01-01T00:00:00+00:00"}).status_code == 422


def test_batch_rolls_back_if_later_row_conflicts(client):
    daily, _ = populate(client)
    new = {**daily[0], "client_record_id": "new-old-day", "observed_on": (datetime.now(timezone.utc).date() - timedelta(days=20)).isoformat()}
    changed = {**daily[1], "sleep_hours": 3}
    assert client.post("/api/v1/risk/daily/batch", json={"records": [new, changed]}).status_code == 409
    assert client.get("/api/v1/risk/history/R1?kind=daily").json()["total"] == 14


def test_backdated_report_cannot_leak_into_historical_prediction(client):
    before = datetime.now(timezone.utc) - timedelta(seconds=1)
    populate(client)
    result = evaluate(client, as_of=before.isoformat()).json()
    assert result["status"] == "insufficient_history"
    assert result["snapshot"]["daily_report_count"] == 0
    assert result["risk"] is None


def test_prediction_is_frozen_and_replayed_after_new_ingestion(client):
    daily, _ = populate(client, limited=True)
    first = evaluate(client).json()
    assert first["snapshot"]["daily_report_count"] == 7
    response = client.post("/api/v1/risk/daily/batch", json={"records": daily[:7]})
    assert response.status_code == 201
    assert evaluate(client).json() == first
    second = evaluate(client, prediction_id="p2").json()
    assert second["snapshot"]["daily_report_count"] == 14
    assert first["snapshot_sha256"] != second["snapshot_sha256"]
    assert evaluate(client, as_of=datetime.now(timezone.utc).isoformat()).status_code == 409


def test_real_local_data_does_not_receive_a_synthetic_probability(client, monkeypatch):
    client.app.state.settings.enable_research_mode = True
    populate(client, source="local_research")
    monkeypatch.setattr(client.app.state.risk_model, "predict", lambda _: (_ for _ in ()).throw(AssertionError("Synthetic model must not be called for local records")))
    result = evaluate(client).json()
    assert result["status"] == "awaiting_source_matched_model" and result["risk"] is None
    assert result["evidence"]["model_applied"] is False
    assert result["snapshot"]["daily_report_count"] == 14


def test_missing_model_returns_explicit_unavailable_not_dummy_score(client, tmp_path):
    populate(client)
    client.app.state.risk_model = RiskModel(tmp_path).load()
    result = evaluate(client).json()
    assert result["status"] == "model_unavailable" and result["risk"] is None


def test_invalid_values_dates_consent_and_mixed_source(client):
    daily, weekly = populate(client)
    assert client.post("/api/v1/risk/daily", json={**daily[0], "consent": False}).status_code == 403
    assert client.post("/api/v1/risk/daily", json={**daily[0], "completed_tasks": 50}).status_code == 422
    assert client.post("/api/v1/risk/daily", json={**daily[0], "late_study_minutes": 961}).status_code == 422
    assert client.post("/api/v1/risk/daily", json={**daily[0], "reported_at": "2026-01-01T12:00:00"}).status_code == 422
    assert client.post("/api/v1/risk/weekly", json={**weekly[0], "exhaustion": "5"}).status_code == 422
    assert client.post("/api/v1/risk/daily", json={**daily[0], "data_source": "local_research"}).status_code == 409
    assert client.get("/api/v1/risk/features/R1?as_of=2026-01-01T00:00:00").status_code == 422
    assert evaluate(client, as_of=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()).status_code == 422
    client.headers["X-API-Key"] = "wrong"
    assert evaluate(client).status_code == 401


def test_history_export_delete_and_training_serving_feature_parity(client):
    populate(client)
    result = evaluate(client).json()
    export = client.get("/api/v1/participants/R1/export").json()
    assert len(export["risk_daily"]) == 14 and len(export["risk_weekly"]) == 2 and len(export["risk_predictions"]) == 1
    pure = snapshot(export["risk_daily"], export["risk_weekly"], parse_time(result["as_of"]))
    assert pure["features"] == result["snapshot"]["features"]
    assert client.get("/api/v1/risk/history/R1?kind=daily&limit=3&offset=1").json()["total"] == 14
    assert client.delete("/api/v1/participants/R1").status_code == 204
    assert client.get("/api/v1/risk/history/R1").status_code == 404


def test_purged_group_and_calendar_training_split_audit(client):
    report = client.get("/api/v1/risk/evaluation").json()
    assert report["synthetic_only"] is True
    assert not set(report["train_participants"]) & set(report["test_participants"])
    cutoff = parse_time(report["global_training_label_cutoff"])
    for fold in report["cv_folds"]:
        assert not set(fold["train_participants"]) & set(fold["validation_participants"])
        assert parse_time(fold["max_train_label_time"]) <= parse_time(fold["training_labels_available_by"])
        assert fold["min_validation_issue_date"] > fold["training_labels_available_by"][:10]
    manifest = json.loads((ROOT / "models/risk/split_manifest.json").read_text())
    for row in manifest:
        if row["split"] == "train":
            assert parse_time(row["label_available_at"]) <= cutoff
        if row["split"] == "test":
            assert parse_time(row["as_of"]).astimezone(ZoneInfo("Asia/Colombo")).date() > cutoff.astimezone(ZoneInfo("Asia/Colombo")).date()
    assert client.get("/api/v1/models").json()["risk"]["trained_burnout_model"] is False


def test_model_checksum_failure_and_demo_page(client, tmp_path):
    import shutil
    shutil.copy(ROOT / "models/risk/model_card.json", tmp_path)
    (tmp_path / "model.joblib").write_bytes(b"corrupt")
    assert RiskModel(tmp_path).load().pipeline is None
    assert client.get("/risk-demo").status_code == 200
