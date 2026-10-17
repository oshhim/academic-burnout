import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.dependencies import get_db
from app.facial.service import fail, participant
from app.models import RiskDaily, RiskPrediction, RiskWeekly
from app.risk.features import BEHAVIOR_FEATURES, FEATURE_NAMES, FEATURE_SCHEMA
from app.risk.schemas import DailyBatch, DailyInput, RiskRequest, STUDY_TIMEZONE, WeeklyInput
from app.risk.service import commit_observations, feature_snapshot, ingest, observation_json, predict

router = APIRouter(prefix="/risk", tags=["Component 3 - longitudinal exploratory proxy"])


@router.get("/config")
def config():
    return {"feature_schema_version": FEATURE_SCHEMA, "feature_names": FEATURE_NAMES, "behavior_only_features": BEHAVIOR_FEATURES,
            "study_timezone": STUDY_TIMEZONE, "complete_daily_lookback": 14, "weekly_lookback_days": 28, "horizon_days": 7,
            "minimum_daily_reports": 7, "minimum_behavior_days": 7, "minimum_nonmissing_predictors": 10,
            "target": "next_weekly_exhaustion_ge4_within_next7days", "instrument": "exploratory-exhaustion-item-v1",
            "instrument_validated": False, "server_ingestion_time_cannot_be_supplied_by_client": True,
            "synthetic_model_used_for_local_records": False}


@router.get("/model")
def model(request: Request):
    return {**request.app.state.risk_model.status(), "model_card": request.app.state.risk_model.card}


@router.get("/evaluation")
def evaluation(request: Request):
    path = request.app.state.risk_model.directory / "evaluation.json"
    if not path.exists():
        fail(503, "risk_evaluation_unavailable", "Run the risk training pipeline.")
    return json.loads(path.read_text())


def store_records(db, records, kind, settings):
    try:
        rows = [ingest(db, record, kind, settings) for record in records]
        commit_observations(db)
    except IntegrityError:
        db.rollback()
        fail(409, "concurrent_observation_conflict", "A day/client ID was written concurrently. Retry the unchanged request.")
    return rows


@router.post("/daily", status_code=201)
def daily(payload: DailyInput, request: Request, db: Session = Depends(get_db)):
    return store_records(db, [payload], "daily", request.app.state.settings)[0]


@router.post("/daily/batch", status_code=201)
def daily_batch(payload: DailyBatch, request: Request, db: Session = Depends(get_db)):
    rows = store_records(db, payload.records, "daily", request.app.state.settings)
    return {"count": len(rows), "records": rows}


@router.post("/weekly", status_code=201)
def weekly(payload: WeeklyInput, request: Request, db: Session = Depends(get_db)):
    return store_records(db, [payload], "weekly", request.app.state.settings)[0]


@router.post("/predictions", status_code=201)
def predictions(payload: RiskRequest, request: Request, db: Session = Depends(get_db)):
    return predict(db, payload, request.app.state.settings, request.app.state.risk_model)


@router.get("/features/{participant_id}")
def features(participant_id: str, as_of: datetime | None = None, db: Session = Depends(get_db)):
    try:
        validated = RiskRequest(participant_id=participant_id, client_prediction_id="feature-preview", as_of=as_of)
    except ValidationError:
        fail(422, "invalid_snapshot_time", "Use a timezone-aware as_of timestamp that is not in the future.")
    owner = participant(db, participant_id)
    return feature_snapshot(db, owner, validated.as_of or datetime.now(timezone.utc))


@router.get("/history/{participant_id}")
def history(participant_id: str, kind: str = Query(default="predictions", pattern="^(daily|weekly|predictions)$"),
            limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    participant(db, participant_id)
    table = {"daily": RiskDaily, "weekly": RiskWeekly, "predictions": RiskPrediction}[kind]
    where = table.participant_id == participant_id
    order = table.created_at if kind == "predictions" else table.observed_on
    rows = db.scalars(select(table).where(where).order_by(order.desc(), table.id).offset(offset).limit(limit)).all()
    return {"participant_id": participant_id, "kind": kind, "total": db.scalar(select(func.count()).select_from(table).where(where)),
            "limit": limit, "offset": offset, "records": [r.result if kind == "predictions" else observation_json(r) for r in rows]}
