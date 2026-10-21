from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.facial.service import fail, now, participant
from app.models import Participant, FacialBaseline, FacialSession, SelfReport, VoiceSession, RiskDaily, RiskWeekly, RiskPrediction
from app.schemas import ParticipantCreate
from app.models import InterventionPreference, InterventionRecommendation, InterventionSession, InterventionEvent, InterventionFeedback, InterventionDemoContext
from app.interventions.service import preference_json, session_json

router = APIRouter(prefix="/participants", tags=["Shared - participants"])


@router.post("", status_code=201)
def register(payload: ParticipantCreate, request: Request, db: Session = Depends(get_db)):
    if not payload.consent:
        fail(403, "consent_required", "Explicit consent is required.")
    if payload.data_source == "local_research" and not request.app.state.settings.enable_research_mode:
        fail(403, "research_mode_disabled", "Local research collection is disabled in this demonstration installation.")
    old = db.get(Participant, payload.participant_id)
    if old:
        if old.data_source != payload.data_source or old.consent_version != payload.consent_version:
            fail(409, "participant_conflict", "Existing participant has different provenance or consent version.")
        return {"participant_id": old.id, "data_source": old.data_source, "created_at": old.created_at}
    row = Participant(id=payload.participant_id, data_source=payload.data_source, created_at=now(), consent_version=payload.consent_version)
    db.add(row)
    db.commit()
    return {"participant_id": row.id, "data_source": row.data_source, "created_at": row.created_at}


@router.get("/{participant_id}/export")
def export(participant_id: str, db: Session = Depends(get_db)):
    owner = participant(db, participant_id)
    sessions = db.scalars(select(FacialSession).where(FacialSession.participant_id == owner.id).order_by(FacialSession.recorded_at)).all()
    baselines = db.scalars(select(FacialBaseline).where(FacialBaseline.participant_id == owner.id)).all()
    reports = db.scalars(select(SelfReport).where(SelfReport.participant_id == owner.id)).all()
    voice = db.scalars(select(VoiceSession).where(VoiceSession.participant_id == owner.id).order_by(VoiceSession.created_at)).all()
    daily = db.scalars(select(RiskDaily).where(RiskDaily.participant_id == owner.id).order_by(RiskDaily.observed_on)).all()
    weekly = db.scalars(select(RiskWeekly).where(RiskWeekly.participant_id == owner.id).order_by(RiskWeekly.observed_on)).all()
    risk = db.scalars(select(RiskPrediction).where(RiskPrediction.participant_id == owner.id).order_by(RiskPrediction.created_at)).all()
    return {
        "participant_id": owner.id, "data_source": owner.data_source, "consent_version": owner.consent_version,
        "facial_sessions": [{"input": r.features, "result": r.result} for r in sessions],
        "baselines": [r.summary for r in baselines],
        "self_reports": [{"session_id": r.session_id, "ratings": r.ratings} for r in reports],
        "voice_sessions": [{"metadata": r.metadata_json, "result": r.result} for r in voice],
        "risk_daily": [{**r.payload, "record_id": r.id, "ingested_at": r.ingested_at} for r in daily],
        "risk_weekly": [{**r.payload, "record_id": r.id, "ingested_at": r.ingested_at} for r in weekly],
        "risk_predictions": [r.result for r in risk],
        "intervention_preferences": [preference_json(r) for r in db.scalars(select(InterventionPreference).where(InterventionPreference.participant_id == owner.id).order_by(InterventionPreference.version)).all()],
        "intervention_recommendations": [r.result for r in db.scalars(select(InterventionRecommendation).where(InterventionRecommendation.participant_id == owner.id).order_by(InterventionRecommendation.created_at)).all()],
        "intervention_sessions": [session_json(r) for r in db.scalars(select(InterventionSession).where(InterventionSession.participant_id == owner.id).order_by(InterventionSession.started_at)).all()],
        "intervention_events": [r.result for r in db.scalars(select(InterventionEvent).where(InterventionEvent.participant_id == owner.id).order_by(InterventionEvent.created_at)).all()],
        "intervention_feedback": [r.result for r in db.scalars(select(InterventionFeedback).where(InterventionFeedback.participant_id == owner.id).order_by(InterventionFeedback.created_at)).all()],
        "intervention_demo_contexts": [r.result for r in db.scalars(select(InterventionDemoContext).where(InterventionDemoContext.participant_id == owner.id).order_by(InterventionDemoContext.created_at)).all()],
    }


@router.delete("/{participant_id}", status_code=204)
def remove(participant_id: str, db: Session = Depends(get_db)):
    participant(db, participant_id)
    # Explicit transaction, scoped to one registered participant.
    for model in (InterventionFeedback, InterventionEvent, InterventionSession, InterventionRecommendation, InterventionPreference, InterventionDemoContext, SelfReport, FacialSession, FacialBaseline, VoiceSession, RiskPrediction, RiskDaily, RiskWeekly):
        db.execute(delete(model).where(model.participant_id == participant_id))
    db.execute(delete(Participant).where(Participant.id == participant_id))
    db.commit()
    return Response(status_code=204)
