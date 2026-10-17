import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.facial.service import fail, fingerprint, iso, now, participant
from app.models import VoiceSession
from app.schemas import Ratings
from app.voice.features import AudioError, FEATURE_SCHEMA, MAX_AUDIO_BYTES, extract_features, extractor_version, feature_names
from app.voice.schemas import VoiceMetadata, VoiceOutput

router = APIRouter(prefix="/voice", tags=["Component 2 - voice acoustics"])
WARNING = "Acted emotion-style classification is not evidence of the speaker's internal emotion, stress, burnout or mental-health state."


def parse_metadata(text, request):
    try:
        payload = VoiceMetadata.model_validate_json(text)
    except ValidationError as exc:
        fail(422, "invalid_voice_metadata", "; ".join(e["msg"] for e in exc.errors()))
    if not payload.consent:
        fail(403, "consent_required", "Explicit consent/permission to process this audio is required.")
    if payload.data_source == "local_research" and not request.app.state.settings.enable_research_mode:
        fail(403, "research_mode_disabled", "Local research collection is disabled.")
    return payload


def audio_bytes(file):
    raw = file.file.read(MAX_AUDIO_BYTES + 1)
    if len(raw) > MAX_AUDIO_BYTES:
        fail(413, "audio_too_large", "Audio limit is 8 MiB.")
    return raw


def analyze(raw, payload, model, include_prediction):
    try:
        quality, features = extract_features(raw)
    except AudioError as exc:
        fail(422, "invalid_audio", str(exc))
    prediction = None
    if features is not None and include_prediction:
        if model.pipeline is None:
            fail(503, "voice_model_unavailable", "Install the supplied model dependencies/artifacts or run training; inspect /api/v1/voice/model.")
        prediction = model.predict(features)
    warnings = [WARNING, "Signal quality uses provisional heuristics; noise, music and non-speech may pass. No speech-content or language detector is implemented.", "Raw audio is not stored by this application; only features, its hash, metadata and results are persisted for check-ins."]
    if payload.data_source == "synthetic_demo":
        warnings.append("SYNTHETIC DEMO input; classification is not research evidence.")
    if payload.data_source == "local_research":
        warnings.append("Natural student speech and Sinhala/Tamil have not been validated with this public-corpus baseline.")
    if quality["duration_sec"] > 8:
        warnings.append("Longer than the short utterances used in RAVDESS; duration-related domain shift is unevaluated.")
    return VoiceOutput(participant_id=payload.participant_id, client_session_id=payload.client_session_id,
        data_source=payload.data_source, submitted_at=now(), recorded_at=iso(payload.recorded_at) if payload.recorded_at else None,
        dataset=payload.dataset, dataset_recording_id=payload.dataset_recording_id, audio_sha256=hashlib.sha256(raw).hexdigest(),
        status=quality["status"], feature_schema_version=FEATURE_SCHEMA, extractor_version=extractor_version(),
        quality=quality, features=features, prediction=prediction, ratings=payload.ratings,
        request_self_report=payload.ratings is None, evidence={"training_data_source": "public_dataset", "training_dataset": "RAVDESS audio speech", "emotion_labels_are_acted": True, "clinical_validation": False, "no_llm_used": True}, warnings=warnings)


@router.get("/config")
def config():
    return {"feature_schema_version": FEATURE_SCHEMA, "extractor_version": extractor_version(), "feature_count": 88,
            "feature_names": feature_names(), "formats": ["WAV"], "duration_sec": [1, 30], "max_audio_bytes": MAX_AUDIO_BYTES,
            "processing_rate": 16000, "speech_detector": False, "threshold_status": "provisional_engineering_settings"}


@router.get("/model")
def model_card(request: Request):
    model = request.app.state.voice_model
    return {**model.status(), "model_card": model.card}


@router.get("/evaluation")
def evaluation(request: Request):
    model = request.app.state.voice_model
    path = model.directory / "evaluation.json"
    if not path.exists():
        fail(503, "evaluation_unavailable", "Run the public-data training pipeline.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/features", response_model=VoiceOutput)
def features(request: Request, metadata: str = Form(...), audio: UploadFile = File(...)):
    payload = parse_metadata(metadata, request)
    return analyze(audio_bytes(audio), payload, request.app.state.voice_model, False)


@router.post("/checkins", response_model=VoiceOutput, status_code=201)
def checkin(request: Request, metadata: str = Form(...), audio: UploadFile = File(...), db: Session = Depends(get_db)):
    payload = parse_metadata(metadata, request)
    owner = participant(db, payload.participant_id)
    if owner.data_source != payload.data_source:
        fail(409, "data_source_mismatch", "Do not mix public, synthetic and local research recordings.")
    raw = audio_bytes(audio)
    digest = fingerprint({"metadata": payload.model_dump(mode="json"), "audio_sha256": hashlib.sha256(raw).hexdigest()})
    def previous():
        old = db.scalar(select(VoiceSession).where(VoiceSession.participant_id == owner.id, VoiceSession.client_session_id == payload.client_session_id))
        if old and old.request_hash != digest:
            fail(409, "session_id_conflict", "Voice client_session_id already has different content.")
        return old
    old = previous()
    if old:
        return old.result
    result = analyze(raw, payload, request.app.state.voice_model, True)
    result.session_id = str(uuid4())
    db.add(VoiceSession(id=result.session_id, participant_id=owner.id, client_session_id=payload.client_session_id,
        request_hash=digest, created_at=result.submitted_at, recorded_at=result.recorded_at, data_source=payload.data_source,
        status=result.status, audio_sha256=result.audio_sha256, model_id=result.prediction["model_id"] if result.prediction else None,
        metadata_json=payload.model_dump(mode="json"), result=result.model_dump(mode="json")))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        old = previous()
        if old:
            return old.result
        raise
    return result


@router.get("/history/{participant_id}")
def history(participant_id: str, limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    participant(db, participant_id)
    where = VoiceSession.participant_id == participant_id
    total = db.scalar(select(func.count()).select_from(VoiceSession).where(where))
    rows = db.scalars(select(VoiceSession).where(where).order_by(VoiceSession.created_at.desc(), VoiceSession.id).offset(offset).limit(limit)).all()
    return {"participant_id": participant_id, "total": total, "limit": limit, "offset": offset, "sessions": [r.result for r in rows]}


@router.post("/self-reports/{session_id}", response_model=Ratings, status_code=201)
def self_report(session_id: str, ratings: Ratings, request: Request, db: Session = Depends(get_db)):
    row = db.get(VoiceSession, session_id)
    if row is None:
        fail(404, "session_not_found", "Unknown voice session ID.")
    if row.data_source == "local_research" and not request.app.state.settings.enable_research_mode:
        fail(403, "research_mode_disabled", "Research label collection is disabled.")
    old = row.result.get("ratings")
    if old and old != ratings.model_dump():
        fail(409, "self_report_conflict", "An immutable voice self-report already exists.")
    row.result = {**row.result, "ratings": ratings.model_dump(), "request_self_report": False}
    db.commit()
    return ratings
