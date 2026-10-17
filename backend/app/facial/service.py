import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.facial.calculations import (
    SCALE_FLOORS, WARNING, aggregate, calculate_baseline, deviation,
    inspect_quality, temporal_measurements,
)
from app.models import FacialBaseline, FacialSession, Participant, SelfReport
from app.schemas import BaselineOutput, Evidence, SessionOutput


def iso(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def now():
    return iso(datetime.now(timezone.utc))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def fail(status, code, message):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def participant(db, participant_id):
    item = db.get(Participant, participant_id)
    if item is None:
        fail(404, "participant_not_found", "Register the participant first.")
    return item


def existing_session(db, payload, digest):
    row = db.scalar(select(FacialSession).where(FacialSession.participant_id == payload.participant_id, FacialSession.client_session_id == payload.client_session_id))
    if row:
        if row.request_hash != digest:
            fail(409, "session_id_conflict", "This client_session_id already has different contents or was used for another operation.")
        return SessionOutput.model_validate(row.result)
    return None


def submit_session(db, payload, kind, allow_research=False):
    owner = participant(db, payload.participant_id)
    if not payload.consent:
        fail(403, "consent_required", "Session feature processing requires explicit consent.")
    if owner.data_source != payload.data_source:
        fail(409, "data_source_mismatch", "Demo and research records cannot be mixed for a participant.")
    if owner.data_source == "local_research" and not allow_research:
        fail(403, "research_mode_disabled", "Research feature collection is disabled.")
    if kind == "calibration" and (payload.protocol != "neutral_only" or not payload.baseline_condition_confirmed):
        fail(422, "invalid_calibration", "Calibration requires neutral_only protocol and participant-confirmed reference conditions.")
    digest = fingerprint({"kind": kind, "payload": payload.model_dump(mode="json")})
    previous = existing_session(db, payload, digest)
    if previous:
        return previous
    quality, valid = inspect_quality(payload)
    accepted = quality.status == "accepted"
    baseline = None
    if kind == "checkin":
        if payload.baseline_id:
            baseline = db.get(FacialBaseline, payload.baseline_id)
            if baseline is None or baseline.participant_id != owner.id:
                fail(404, "baseline_not_found", "The requested baseline does not belong to this participant.")
        else:
            baseline = db.scalar(select(FacialBaseline).where(
                FacialBaseline.participant_id == owner.id,
                FacialBaseline.effective_at <= iso(payload.recorded_at),
            ).order_by(FacialBaseline.version.desc()))
        if baseline is None:
            fail(409, "baseline_required", "Create a baseline from at least three accepted calibration sessions before submitting a check-in.")
        if baseline.effective_at > iso(payload.recorded_at):
            fail(409, "future_baseline", "A check-in cannot use calibration observations from its future.")
        if baseline.summary["extractor_version"] != payload.extractor_version:
            fail(409, "extractor_mismatch", "Use the same extractor version for calibration and check-ins; create a new baseline when the extractor changes.")
    features = aggregate(valid) if accepted else None
    dev = deviation(features, baseline.summary["center"], baseline.summary["scale"]) if accepted and baseline else None
    temporal = temporal_measurements(valid, payload, baseline.summary["center"], baseline.summary["scale"]) if accepted and baseline else None
    warnings = [WARNING, "Quality and deviation thresholds are provisional engineering settings, not clinically validated thresholds."]
    if owner.data_source == "synthetic_demo":
        warnings.append("SYNTHETIC DEMO: this record is not an observation from a real student.")
    if not accepted:
        warnings.append("Insufficient quality: no facial deviation or temporal result was computed.")
    result = SessionOutput(
        session_id=str(uuid4()), participant_id=owner.id, client_session_id=payload.client_session_id,
        data_source=owner.data_source, recorded_at=iso(payload.recorded_at),
        extractor_version=payload.extractor_version, protocol=payload.protocol,
        baseline_condition_confirmed=payload.baseline_condition_confirmed,
        status=quality.status, quality=quality, session_features=features,
        baseline_id=baseline.id if baseline else None, deviation=dev, temporal=temporal,
        request_self_report=payload.ratings is None,
        self_report_reason="Research-stage labels are requested for EVERY session, not only uncertain predictions." if accepted else "Use self-report as fallback; no visual conclusion is available.",
        evidence=Evidence(), warnings=warnings,
    )
    row = FacialSession(
        id=result.session_id, participant_id=owner.id, client_session_id=payload.client_session_id,
        request_hash=digest, recorded_at=result.recorded_at, created_at=now(), kind=kind,
        data_source=owner.data_source, status=result.status, baseline_id=result.baseline_id,
        # Numerical windows only. No identity mesh, image, video, transcript or name.
        features=payload.model_dump(mode="json"), result=result.model_dump(mode="json"),
    )
    db.add(row)
    try:
        db.flush()
        if payload.ratings:
            db.add(SelfReport(session_id=row.id, participant_id=owner.id, created_at=now(), ratings=payload.ratings.model_dump()))
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = existing_session(db, payload, digest)
        if replay:
            return replay
        raise
    return result


def create_baseline(db, payload, allow_research=False):
    owner = participant(db, payload.participant_id)
    if owner.data_source == "local_research" and not allow_research:
        fail(403, "research_mode_disabled", "Research baseline creation is disabled.")
    rows = []
    for sid in payload.session_ids:
        row = db.get(FacialSession, sid)
        if row is None or row.participant_id != owner.id:
            fail(404, "calibration_not_found", "Every calibration session must belong to this participant.")
        if row.kind != "calibration" or row.status != "accepted":
            fail(422, "unusable_calibration", "Only accepted calibration sessions can create a baseline.")
        rows.append(row)
    extractors = {r.features["extractor_version"] for r in rows}
    if len(extractors) != 1:
        fail(409, "extractor_mismatch", "Calibration sessions must use one extractor version.")
    digest = fingerprint({"session_ids": sorted(payload.session_ids), "method": Evidence().model_version})
    old = db.scalar(select(FacialBaseline).where(FacialBaseline.participant_id == owner.id, FacialBaseline.request_hash == digest))
    if old:
        return BaselineOutput.model_validate(old.summary)
    centers, scales = calculate_baseline([r.result["session_features"] for r in rows])
    version = (db.scalar(select(func.max(FacialBaseline.version)).where(FacialBaseline.participant_id == owner.id)) or 0) + 1
    effective_at = max(iso(datetime.fromisoformat(r.recorded_at) + timedelta(seconds=r.result["quality"]["elapsed_duration_sec"])) for r in rows)
    warnings = ["Reference conditions are participant-confirmed, not proof of a healthy or unstressed state.", "Three sessions are a technical minimum; collect several days of calibration and inspect stability."]
    if owner.data_source == "synthetic_demo":
        warnings.append("Synthetic demonstration baseline.")
    result = BaselineOutput(
        baseline_id=str(uuid4()), participant_id=owner.id, data_source=owner.data_source,
        version=version, created_at=now(), effective_at=effective_at, session_ids=sorted(payload.session_ids),
        center=centers, scale=scales, scale_floors=SCALE_FLOORS, extractor_version=next(iter(extractors)),
        evidence=Evidence(), warnings=warnings,
    )
    db.add(FacialBaseline(
        id=result.baseline_id, participant_id=owner.id, created_at=result.created_at,
        effective_at=effective_at, version=version, data_source=owner.data_source,
        request_hash=digest, summary=result.model_dump(mode="json"),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(FacialBaseline).where(FacialBaseline.participant_id == owner.id, FacialBaseline.request_hash == digest))
        if existing:
            return BaselineOutput.model_validate(existing.summary)
        fail(409, "baseline_creation_conflict", "Another baseline was created concurrently. Retry this request.")
    return result
