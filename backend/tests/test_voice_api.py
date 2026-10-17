import hashlib
import io
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from app.voice.model import VoiceModel
from scripts.run_voice_demo import run_voice_demo

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "app/static/voice_samples"
FILE = SAMPLES / "03-01-01-01-01-01-19.wav"


def metadata(pid="VOICE-01", sid="v1", **changes):
    return {"participant_id": pid, "client_session_id": sid, "data_source": "public_dataset", "consent": True, "dataset": "RAVDESS", "dataset_recording_id": FILE.stem, **changes}


def register(client, pid="VOICE-01", source="public_dataset"):
    response = client.post("/api/v1/participants", json={"participant_id": pid, "data_source": source, "consent": True})
    assert response.status_code == 201


def upload(client, *, meta=None, raw=None, endpoint="checkins"):
    return client.post(f"/api/v1/voice/{endpoint}", data={"metadata": json.dumps(meta or metadata())}, files={"audio": ("ignored_filename.wav", FILE.read_bytes() if raw is None else raw, "audio/wav")})


def test_real_public_audio_prediction_features_and_evidence(client):
    register(client)
    response = upload(client)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "accepted" and len(result["features"]) == 88
    assert result["prediction"]["predicted_emotion_style"] in {"neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"}
    assert result["prediction"]["probabilities"] is None
    assert result["audio_sha256"] == hashlib.sha256(FILE.read_bytes()).hexdigest()
    assert result["recorded_at"] is None  # The public corpus capture date is not invented.
    assert result["evidence"]["no_llm_used"] and not result["evidence"]["clinical_validation"]
    history = client.get("/api/v1/voice/history/VOICE-01").json()
    assert history["total"] == 1
    export = client.get("/api/v1/participants/VOICE-01/export").json()
    assert len(export["voice_sessions"]) == 1 and "audio" not in export["voice_sessions"][0]


def test_retry_and_changed_audio_conflict(client):
    register(client)
    first = upload(client)
    assert first.status_code == 201
    assert upload(client).json() == first.json()
    second = (SAMPLES / "03-01-03-01-01-01-19.wav").read_bytes()
    assert upload(client, raw=second).status_code == 409


def test_consent_provenance_source_mixing_and_authorization(client):
    register(client)
    assert upload(client, meta=metadata(consent=False)).status_code == 403
    assert upload(client, meta=metadata(dataset=None)).status_code == 422
    register(client, "DEMO-01", "synthetic_demo")
    assert upload(client, meta=metadata(pid="DEMO-01")).status_code == 409
    client.headers["X-API-Key"] = "wrong"
    assert upload(client).status_code == 401


def test_quality_failure_is_persisted_without_classification(client):
    register(client)
    output = io.BytesIO()
    sf.write(output, np.zeros(32000), 16000, format="WAV")
    result = upload(client, raw=output.getvalue()).json()
    assert result["status"] == "insufficient_quality"
    assert result["features"] is None and result["prediction"] is None and result["request_self_report"]


def test_features_only_and_malformed_audio(client):
    response = upload(client, endpoint="features")
    assert response.status_code == 200 and response.json()["session_id"] is None
    assert len(response.json()["features"]) == 88 and response.json()["prediction"] is None
    assert upload(client, endpoint="features", raw=b"invalid audio").status_code == 422


def test_missing_model_is_explicit_and_features_still_work(client, tmp_path):
    register(client)
    client.app.state.voice_model = VoiceModel(tmp_path).load()
    assert client.get("/api/v1/voice/model").json()["status"] == "unavailable"
    assert upload(client).status_code == 503
    assert upload(client, endpoint="features").status_code == 200


def test_public_demo_history_ratings_and_deletion(client):
    report = run_voice_demo(client, "VOICE-DEMO")
    assert report["history_total"] == 3
    session_id = report["results"][0]["response"]["session_id"]
    endpoint = f"/api/v1/voice/self-reports/{session_id}"
    ratings = {"fatigue": 2, "mental_strain": 3, "concentration_readiness": 4}
    assert client.post(endpoint, json=ratings).status_code == 201
    assert client.post(endpoint, json=ratings).status_code == 201
    assert client.post(endpoint, json={**ratings, "fatigue": 5}).status_code == 409
    assert client.get("/api/v1/participants/VOICE-DEMO/export").json()["voice_sessions"][0]["result"]["ratings"] == ratings
    assert client.delete("/api/v1/participants/VOICE-DEMO").status_code == 204
    assert client.get("/api/v1/voice/history/VOICE-DEMO").status_code == 404


def test_research_collection_disabled_and_metadata_timestamps(client):
    data = metadata(data_source="local_research", dataset=None, dataset_recording_id=None, recorded_at="2026-10-10T10:00:00+00:00")
    assert upload(client, endpoint="features", meta=data).status_code == 403
    data["recorded_at"] = "2026-10-10T10:00:00"
    assert upload(client, endpoint="features", meta=data).status_code == 422


def test_model_report_split_integrity_and_no_test_selection(client):
    report = client.get("/api/v1/voice/evaluation").json()
    assert report["source_files"] == 1440 and report["no_synthetic_training_data"]
    assert not set(report["train_actors"]) & set(report["test_actors"])
    for fold in report["cv_folds"]:
        assert not set(fold["train_actors"]) & set(fold["validation_actors"])
        assert set(fold["train_actors"]) | set(fold["validation_actors"]) <= set(report["train_actors"])
    names = [n for n in report["comparisons"] if not n.startswith("dummy")]
    selected = max(names, key=lambda n: report["comparisons"][n]["cv_macro_f1_mean"])
    assert report["selected_model"] == selected
    manifest = json.loads((ROOT / "models/voice/dataset_manifest.json").read_text())
    accepted_test = [r for r in manifest if r["split"] == "test" and r["quality"]["status"] == "accepted"]
    assert len(accepted_test) == report["test_samples"]
    assert set(x["actor"] for x in accepted_test) == set(report["test_actors"])


def test_corrupted_artifact_is_not_loaded(tmp_path):
    import shutil
    shutil.copy(ROOT / "models/voice/model_card.json", tmp_path)
    (tmp_path / "model.joblib").write_bytes(b"corrupted")
    model = VoiceModel(tmp_path).load()
    assert model.pipeline is None and model.reason == "model_artifact_or_dependency_incompatible"


def test_demo_sample_path_is_allowlisted(client):
    manifest = client.get("/voice-demo/samples").json()
    assert manifest["license"] == "CC-BY-NC-SA-4.0"
    assert client.get("/voice-demo/audio/" + manifest["samples"][0]["filename"]).status_code == 200
    assert client.get("/voice-demo/audio/model.joblib").status_code == 404
    assert client.get("/voice-demo").status_code == 200


def test_voice_upload_has_separate_byte_limit_from_json_requests(client):
    register(client, source="synthetic_demo")
    meta = metadata(data_source="synthetic_demo", dataset=None, dataset_recording_id=None)
    output = io.BytesIO()
    sf.write(output, np.zeros((48000 * 10, 2)), 48000, format="WAV", subtype="PCM_16")
    raw = output.getvalue()
    assert len(raw) > 1048576
    response = upload(client, meta=meta, raw=raw)
    assert response.status_code == 201 and response.json()["status"] == "insufficient_quality"
    meta["client_session_id"] = "too-large"
    assert upload(client, meta=meta, raw=b"x" * (8 * 1024 * 1024 + 1)).status_code == 413
