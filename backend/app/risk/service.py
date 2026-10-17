from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.facial.service import fail, fingerprint, iso, now, participant
from app.models import FacialSession, RiskDaily, RiskPrediction, RiskWeekly, VoiceSession
from app.risk.features import parse_time, snapshot
from app.risk.schemas import STUDY_TIMEZONE

WARNING = "This estimates an exploratory self-reported exhaustion proxy, not burnout, diagnosis or a validated mental-health risk probability."


def observation_json(row):
    return {**row.payload, "record_id": row.id, "ingested_at": row.ingested_at}


def require_owner(db, pid, source, settings):
    owner = participant(db, pid)
    if owner.data_source != source:
        fail(409, "data_source_mismatch", "The observation source must match the registered participant.")
    if source == "local_research" and not settings.enable_research_mode:
        fail(403, "research_mode_disabled", "Local longitudinal collection is disabled.")
    return owner


def ingest(db, payload, kind, settings):
    require_owner(db, payload.participant_id, payload.data_source, settings)
    if not payload.consent:
        fail(403, "consent_required", "Explicit consent is required for each submitted observation.")
    table = RiskDaily if kind == "daily" else RiskWeekly
    serialized = payload.model_dump(mode="json")
    digest = fingerprint(serialized)
    old = db.scalar(select(table).where(table.participant_id == payload.participant_id,
        or_(table.client_record_id == payload.client_record_id, table.observed_on == payload.observed_on.isoformat())))
    if old:
        if old.request_hash != digest:
            fail(409, "observation_conflict", "This day or client_record_id already contains different immutable data.")
        return observation_json(old)
    row = table(id=str(uuid4()), participant_id=payload.participant_id, client_record_id=payload.client_record_id,
                request_hash=digest, data_source=payload.data_source, observed_on=payload.observed_on.isoformat(),
                reported_at=iso(payload.reported_at), ingested_at=now(), payload=serialized)
    db.add(row)
    # The caller commits once; a whole batch succeeds or rolls back.
    db.flush()
    return observation_json(row)


def commit_observations(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "concurrent_observation_conflict", "A concurrent submission wrote the same day/client ID; retry the unchanged request.")


def feature_snapshot(db, owner, as_of):
    cutoff = iso(as_of)
    local_day = as_of.astimezone(ZoneInfo(STUDY_TIMEZONE)).date()
    daily = db.scalars(select(RiskDaily).where(RiskDaily.participant_id == owner.id, RiskDaily.data_source == owner.data_source,
        RiskDaily.observed_on >= (local_day - timedelta(days=14)).isoformat(), RiskDaily.observed_on < local_day.isoformat(),
        RiskDaily.reported_at <= cutoff, RiskDaily.ingested_at <= cutoff)).all()
    weekly = db.scalars(select(RiskWeekly).where(RiskWeekly.participant_id == owner.id, RiskWeekly.data_source == owner.data_source,
        RiskWeekly.observed_on >= (local_day - timedelta(days=28)).isoformat(), RiskWeekly.observed_on <= local_day.isoformat(),
        RiskWeekly.reported_at <= cutoff, RiskWeekly.ingested_at <= cutoff)).all()
    result = snapshot([observation_json(r) for r in daily], [observation_json(r) for r in weekly], as_of)
    faces = db.scalars(select(FacialSession).where(FacialSession.participant_id == owner.id, FacialSession.status == "accepted", FacialSession.created_at <= cutoff)).all()
    voice = db.scalars(select(VoiceSession).where(VoiceSession.participant_id == owner.id, VoiceSession.status == "accepted", VoiceSession.created_at <= cutoff)).all()
    def in_window(at):
        event_day = parse_time(at).astimezone(ZoneInfo(STUDY_TIMEZONE)).date()
        return result["lookback_start"] <= event_day.isoformat() <= result["lookback_end"]
    result["modality_context"] = {"facial_accepted_sessions_in_window": sum(in_window(r.recorded_at) for r in faces),
                                  "voice_accepted_sessions_in_window": sum(in_window(r.recorded_at or r.created_at) for r in voice),
                                  "facial_or_voice_used_as_risk_predictors": False,
                                  "reason": "Availability is reported; visual deviation/acted emotion are not validated exhaustion probabilities and are not fused in this baseline."}
    return result


def predict(db, payload, settings, model):
    owner = participant(db, payload.participant_id)
    if owner.data_source not in {"synthetic_demo", "local_research"}:
        fail(422, "unsupported_longitudinal_source", "No public exhaustion-label dataset adapter is configured; do not relabel speech emotion as exhaustion.")
    require_owner(db, owner.id, owner.data_source, settings)
    digest = fingerprint(payload.model_dump(mode="json"))
    previous = db.scalar(select(RiskPrediction).where(RiskPrediction.participant_id == owner.id, RiskPrediction.client_prediction_id == payload.client_prediction_id))
    if previous:
        if previous.request_hash != digest:
            fail(409, "prediction_id_conflict", "This client_prediction_id already used a different cutoff/request.")
        return previous.result
    as_of = payload.as_of or datetime.now(timezone.utc)
    snap = feature_snapshot(db, owner, as_of)
    warnings = [WARNING, "The single-item weekly exhaustion scale and the 0.5 display threshold are exploratory, not validated clinical instruments/cutoffs."]
    risk = None
    if snap["status"] == "insufficient_history":
        status = "insufficient_history"
    elif model.pipeline is None:
        status = "model_unavailable"
    elif model.card["training_data_source"] != owner.data_source:
        status = "awaiting_source_matched_model"
        warnings.append("The supplied synthetic model is not used to assign a real student's probability. Real/local model validation is still required.")
    else:
        risk = model.predict(snap["features"])
        status = "demo_only_prediction" if owner.data_source == "synthetic_demo" else "exploratory_local_prediction"
    if owner.data_source == "synthetic_demo":
        warnings.append("SYNTHETIC DEMO: observations/outcomes and trained risk probabilities are technical fixtures, not measured student evidence.")
    result = {"prediction_id": str(uuid4()), "participant_id": owner.id, "client_prediction_id": payload.client_prediction_id,
              "created_at": now(), "as_of": iso(as_of), "data_source": owner.data_source, "status": status,
              "snapshot": snap, "snapshot_sha256": fingerprint(snap), "risk": risk,
              "evidence": {"model_status": model.status(), "training_data_source": model.card["training_data_source"] if model.card else None,
                           "model_applied": risk is not None,
                           "forecast_target": "next_weekly_exhaustion_ge4_within_next7days", "clinical_validation": False,
                           "instrument_validated": False, "knowledge_cutoff_enforced": True,
                           "features_use_prior_complete_days": True, "no_llm_used": True}, "warnings": warnings}
    db.add(RiskPrediction(id=result["prediction_id"], participant_id=owner.id, client_prediction_id=payload.client_prediction_id,
        request_hash=digest, created_at=result["created_at"], as_of=result["as_of"], data_source=owner.data_source,
        model_id=risk["model_id"] if risk else None, status=status, snapshot_hash=result["snapshot_sha256"], result=result))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "concurrent_prediction_conflict", "A concurrent request used this prediction ID. Retry the unchanged request.")
    return result
