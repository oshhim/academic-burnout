import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.facial.service import fail, participant
from app.interventions import service, context as component_context
from app.interventions.catalog import ACTIVITIES, CATALOG_VERSION, NOTICE
from app.interventions.policy import status
from app.interventions.schemas import DemoContextInput, EventInput, FeedbackInput, PreferenceInput, RecommendationInput, StartInput
from app.models import InterventionPreference, InterventionRecommendation, InterventionSession, InterventionEvent, InterventionFeedback

router = APIRouter(prefix="/interventions", tags=["Component 4 - preference and feedback recommendations"])


@router.get("/catalog")
def catalog():
    return {"version": CATALOG_VERSION, "activities": ACTIVITIES, "notice": NOTICE}


@router.get("/policy")
def policy():
    return {**status(), "formula": {"generic": "base = 0.7*goal_match + 0.3*(1-duration/available_seconds)",
            "preference": "0.55*base + 0.45*category_preference", "adaptive": "U - R, U=0.55*base+0.25*preference+0.20*shrunk_helpfulness",
            "multimodal_weighted": "(1-lambda)*U + lambda*sum(alpha_j*compatibility_j(activity)) - R; lambda=0.25 with eligible context, else 0"},
            "component_weights": component_context.BASE_WEIGHTS, "context_share": component_context.CONTEXT_SHARE,
            "mapping_version": component_context.MAPPING_VERSION, "compatibility_maps": component_context.COMPATIBILITY,
            "context_max_age_seconds": component_context.MAX_AGE_SECONDS,
            "context_scope": "synthetic_demo only; source-matched completed/accepted results or explicit C4-only fixtures",
            "category_preference": "(rating-1)/4, default rating=3", "shrunk_helpfulness": "(1.5 + sum((helpfulness-1)/4))/(3+n)",
            "feedback_window": "90 days, last 20 completed-session ratings per activity, same participant and source",
            "recent_repeat_penalty": "0.05 if started in past 7 days; adaptive and multimodal_weighted", "tie_break": "activity_id ascending",
            "hard_constraints": ["available time", "preference duration limit", "explicit exclusions", "movement permission", "audio permission"],
            "offer_expires_after_hours": 24, "score_is_health_probability": False, "notice": NOTICE}


@router.get("/evaluation")
def evaluation():
    path = Path(__file__).resolve().parents[2] / "models/interventions/evaluation.json"
    if not path.exists():
        fail(503, "simulation_unavailable", "Run python -m training.evaluate_interventions")
    return json.loads(path.read_text())


@router.get("/evaluation/optional-context")
def optional_context_evaluation():
    path = Path(__file__).resolve().parents[2] / "models/interventions/optional_context_evaluation.json"
    if not path.exists():
        fail(503, "context_audit_unavailable", "Run python -m training.evaluate_optional_context")
    return json.loads(path.read_text())


@router.post("/preferences", status_code=201)
def preferences(payload: PreferenceInput, request: Request, db: Session = Depends(get_db)):
    return service.save_preferences(db, payload, request.app.state.settings)


@router.get("/context/{participant_id}")
def get_context(participant_id: str, demo_context_id: str | None = None, db: Session = Depends(get_db)):
    return component_context.resolve(db, participant(db, participant_id), datetime.now(timezone.utc), demo_context_id=demo_context_id)


@router.post("/demo-contexts", status_code=201)
def demo_contexts(payload: DemoContextInput, request: Request, db: Session = Depends(get_db)):
    return service.save_demo_context(db, payload, request.app.state.settings)


@router.get("/state/{participant_id}")
def get_state(participant_id: str, db: Session = Depends(get_db)):
    return service.current_state(db, participant(db, participant_id))


@router.get("/preferences/{participant_id}")
def get_preferences(participant_id: str, db: Session = Depends(get_db)):
    return service.current_preferences(db, participant(db, participant_id))


@router.post("/recommendations", status_code=201)
def recommendations(payload: RecommendationInput, request: Request, db: Session = Depends(get_db)):
    return service.recommend(db, payload, request.app.state.settings)


@router.get("/recommendations/{participant_id}/{recommendation_id}")
def get_recommendation(participant_id: str, recommendation_id: str, db: Session = Depends(get_db)):
    return service.owned(db, InterventionRecommendation, recommendation_id, participant(db, participant_id)).result


@router.post("/sessions", status_code=201)
def sessions(payload: StartInput, request: Request, db: Session = Depends(get_db)):
    return service.start(db, payload, request.app.state.settings)


@router.get("/sessions/{participant_id}/{session_id}")
def get_session(participant_id: str, session_id: str, db: Session = Depends(get_db)):
    return service.session_json(service.owned(db, InterventionSession, session_id, participant(db, participant_id)))


@router.post("/events", status_code=201)
def events(payload: EventInput, request: Request, db: Session = Depends(get_db)):
    return service.finish(db, payload, request.app.state.settings)


@router.post("/feedback", status_code=201)
def feedback(payload: FeedbackInput, request: Request, db: Session = Depends(get_db)):
    return service.feedback(db, payload, request.app.state.settings)


@router.get("/metrics/{participant_id}")
def metrics(participant_id: str, db: Session = Depends(get_db)):
    return service.metrics(db, participant(db, participant_id))


@router.get("/history/{participant_id}")
def history(participant_id: str, kind: str = Query(default="recommendations", pattern="^(preferences|recommendations|sessions|events|feedback)$"),
            limit: int = Query(default=30, ge=1, le=100), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    owner = participant(db, participant_id)
    table = {"preferences": InterventionPreference, "recommendations": InterventionRecommendation, "sessions": InterventionSession, "events": InterventionEvent, "feedback": InterventionFeedback}[kind]
    where = table.participant_id == owner.id
    order = table.started_at if kind == "sessions" else table.created_at
    rows = db.scalars(select(table).where(where).order_by(order.desc(), table.id).offset(offset).limit(limit)).all()
    mapper = service.preference_json if kind == "preferences" else service.session_json if kind == "sessions" else lambda row: row.result
    return {"participant_id": owner.id, "kind": kind, "total": db.scalar(select(func.count()).select_from(table).where(where)),
            "limit": limit, "offset": offset, "records": [mapper(r) for r in rows]}
