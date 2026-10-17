from datetime import datetime, timedelta, timezone

from scripts.facial_demo_data import calibration_sessions, session
from scripts.run_facial_demo import run_facial_demo


def register(client, pid="P1"):
    response = client.post("/api/v1/participants", json={"participant_id": pid, "consent": True})
    assert response.status_code == 201, response.text


def calibrated(client, pid="P1"):
    register(client, pid)
    ids = []
    for payload in calibration_sessions(pid):
        response = client.post("/api/v1/facial/calibrations", json=payload)
        assert response.status_code == 201, response.text
        ids.append(response.json()["session_id"])
    response = client.post("/api/v1/facial/baselines", json={"participant_id": pid, "session_ids": ids})
    assert response.status_code == 201, response.text
    return ids, response.json()


def test_full_demo_rejection_and_history_export_deletion(client):
    report = run_facial_demo(client, "DEMO-test")
    results = report["scenarios"]
    assert results["return"]["temporal"]["return_fraction"] > 0
    assert results["persistent"]["temporal"]["return_fraction"] < 0
    assert results["poor_quality"]["deviation"] is None
    assert results["poor_quality"]["session_features"] is None
    assert results["poor_quality"]["request_self_report"] is True
    assert results["stable"]["data_source"] == "synthetic_demo"
    history = client.get("/api/v1/facial/history/DEMO-test?limit=2&offset=1").json()
    assert history["total"] == 4 and len(history["sessions"]) == 2
    export = client.get("/api/v1/participants/DEMO-test/export").json()
    assert len(export["facial_sessions"]) == 7 and len(export["baselines"]) == 1
    assert client.delete("/api/v1/participants/DEMO-test").status_code == 204
    assert client.get("/api/v1/participants/DEMO-test/export").status_code == 404


def test_key_health_models_headers_and_page(client):
    assert client.get("/health", headers={"X-API-Key": "bad"}).status_code == 200
    assert client.get("/api/v1/models", headers={"X-API-Key": "bad"}).status_code == 401
    response = client.get("/api/v1/models")
    assert response.headers["X-Request-ID"]
    assert response.json()["voice"]["status"] in {"ready", "unavailable"}
    assert client.get("/").status_code == 200


def test_consent_and_research_gate(client):
    assert client.post("/api/v1/participants", json={"participant_id": "P1", "consent": False}).status_code == 403
    assert client.post("/api/v1/participants", json={"participant_id": "P2", "consent": True, "data_source": "local_research"}).status_code == 403
    register(client)
    payload = session("P1", "calibration-0", calibration=True)
    payload["consent"] = False
    assert client.post("/api/v1/facial/calibrations", json=payload).status_code == 403


def test_disabling_research_stops_existing_participant_collection(client):
    client.app.state.settings.enable_research_mode = True
    response = client.post("/api/v1/participants", json={"participant_id": "LOCAL-01", "data_source": "local_research", "consent": True})
    assert response.status_code == 201
    payload = session("LOCAL-01", "calibration-0", calibration=True, source="local_research")
    accepted = client.post("/api/v1/facial/calibrations", json=payload)
    assert accepted.status_code == 201
    client.app.state.settings.enable_research_mode = False
    payload["client_session_id"] = "calibration-1"
    assert client.post("/api/v1/facial/calibrations", json=payload).status_code == 403
    ratings = {"fatigue": 2, "mental_strain": 3, "concentration_readiness": 4}
    assert client.post(f"/api/v1/facial/self-reports/{accepted.json()["session_id"]}", json=ratings).status_code == 403
    # Withdrawal/export stay available, even after collection is disabled.
    assert client.get("/api/v1/participants/LOCAL-01/export").status_code == 200


def test_missing_baseline_and_source_mixing(client):
    register(client)
    assert client.post("/api/v1/facial/checkins", json=session("P1", "s1")).status_code == 409
    payload = session("P1", "calibration-0", calibration=True, source="local_research")
    assert client.post("/api/v1/facial/calibrations", json=payload).status_code == 409


def test_reference_confirmation_and_minimum_and_owner(client):
    register(client)
    payload = session("P1", "calibration-0", calibration=True)
    payload["baseline_condition_confirmed"] = False
    assert client.post("/api/v1/facial/calibrations", json=payload).status_code == 422
    ids, baseline = calibrated(client, "P2")
    assert client.post("/api/v1/facial/baselines", json={"participant_id": "P2", "session_ids": ids[:2]}).status_code == 422
    assert client.post("/api/v1/facial/baselines", json={"participant_id": "P1", "session_ids": ids}).status_code == 404
    data = session("P1", "s1")
    data["baseline_id"] = baseline["baseline_id"]
    assert client.post("/api/v1/facial/checkins", json=data).status_code == 404


def test_idempotent_retries_and_changed_content_conflict(client):
    register(client)
    payload = calibration_sessions("P1")[0]
    first = client.post("/api/v1/facial/calibrations", json=payload)
    retry = client.post("/api/v1/facial/calibrations", json=payload)
    assert first.status_code == 201 and first.json() == retry.json()
    payload["windows"][0]["features"]["jaw_open"] += 0.1
    assert client.post("/api/v1/facial/calibrations", json=payload).status_code == 409


def test_baseline_immutable_dedup_and_old_results_keep_version(client):
    ids, baseline = calibrated(client)
    retry = client.post("/api/v1/facial/baselines", json={"participant_id": "P1", "session_ids": ids[::-1]}).json()
    assert retry == baseline
    payload = session("P1", "first-check")
    initial = client.post("/api/v1/facial/checkins", json=payload).json()
    new = session("P1", "calibration-4", calibration=True, at=datetime.now(timezone.utc) - timedelta(hours=2))
    c = client.post("/api/v1/facial/calibrations", json=new).json()
    latest = client.post("/api/v1/facial/baselines", json={"participant_id": "P1", "session_ids": [*ids, c["session_id"]]}).json()
    assert latest["version"] == 2
    assert client.get("/api/v1/facial/history/P1").json()["sessions"][0]["baseline_id"] == initial["baseline_id"]


def test_future_baseline_and_extractor_change(client):
    _, baseline = calibrated(client)
    payload = session("P1", "s1", at=datetime.now(timezone.utc) - timedelta(days=5))
    payload["baseline_id"] = baseline["baseline_id"]
    response = client.post("/api/v1/facial/checkins", json=payload)
    assert response.status_code == 409 and response.json()["error"]["code"] == "future_baseline"
    payload = session("P1", "s2")
    payload["extractor_version"] = "different-extractor"
    assert client.post("/api/v1/facial/checkins", json=payload).status_code == 409


def test_self_report_validation_immutability_and_export(client):
    calibrated(client)
    result = client.post("/api/v1/facial/checkins", json=session("P1", "s1")).json()
    endpoint = f"/api/v1/facial/self-reports/{result["session_id"]}"
    ratings = {"fatigue": 2, "mental_strain": 3, "concentration_readiness": 4}
    assert client.post(endpoint, json={**ratings, "fatigue": "2"}).status_code == 422
    assert client.post(endpoint, json=ratings).status_code == 201
    assert client.get(endpoint).json() == ratings
    assert client.post(endpoint, json={**ratings, "mental_strain": 5}).status_code == 409
    history = client.get("/api/v1/facial/history/P1").json()
    assert history["sessions"][0]["request_self_report"] is False
    assert len(client.get("/api/v1/participants/P1/export").json()["self_reports"]) == 1


def test_request_limit_does_not_echo_feature_contents(client):
    response = client.post("/api/v1/participants", content=b"x" * 1048577)
    assert response.status_code == 413 and response.headers["X-Request-ID"]
    response = client.post("/api/v1/participants", json={"participant_id": "bad space", "consent": True, "unexpected": "private text"})
    assert response.status_code == 422 and "private text" not in response.text


def test_poor_calibration_cannot_be_baseline(client):
    ids, _ = calibrated(client)
    payload = session("P1", "calibration-5", calibration=True, scenario="poor_quality")
    result = client.post("/api/v1/facial/calibrations", json=payload).json()
    assert result["status"] == "insufficient_quality"
    response = client.post("/api/v1/facial/baselines", json={"participant_id": "P1", "session_ids": [*ids[:2], result["session_id"]]})
    assert response.status_code == 422
