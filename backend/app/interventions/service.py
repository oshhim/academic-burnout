from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.facial.service import fail, fingerprint, now, participant
from app.interventions.catalog import BY_ID, CATALOG_VERSION, NOTICE, POLICY_VERSION
from app.interventions.policy import feedback_summary, rank, RECENT_DAYS
from app.interventions.schemas import default_preferences
from app.models import (FacialSession, VoiceSession, RiskPrediction, InterventionPreference as Preference,
                        InterventionRecommendation as Recommendation, InterventionSession as ActivitySession,
                        InterventionEvent as Event, InterventionFeedback as Feedback)


def authorize(db, payload, settings):
    owner = participant(db, payload.participant_id)
    if not payload.consent:
        fail(403, "consent_required", "Explicit consent is required for preferences and activity records.")
    if payload.data_source != owner.data_source:
        fail(409, "data_source_mismatch", "Participant and record provenance must match.")
    if owner.data_source == "local_research" and not settings.enable_research_mode:
        fail(403, "research_mode_disabled", "Local research collection is disabled.")
    return owner


def owned(db, table, row_id, owner):
    row = db.get(table, row_id)
    if row is None or row.participant_id != owner.id:
        fail(404, "record_not_found", "The requested record does not belong to this participant.")
    return row


def replay(db, table, field, value, owner, digest):
    row = db.scalar(select(table).where(table.participant_id == owner.id, getattr(table, field) == value))
    if row is not None and row.request_hash != digest:
        fail(409, "client_id_conflict", "This client ID has different contents. Use the original request or a new ID.")
    return row


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "concurrent_write_conflict", "A unique record was written concurrently. Retry the identical request.")


def preference_json(row):
    return {"preference_id": row.id, "participant_id": row.participant_id, "data_source": row.data_source,
            "version": row.version, "created_at": row.created_at, "preferences": row.payload}


def current_preferences(db, owner):
    row = db.scalar(select(Preference).where(Preference.participant_id == owner.id).order_by(Preference.version.desc()))
    return preference_json(row) if row else {"preference_id": None, "participant_id": owner.id, "data_source": owner.data_source,
                                           "version": 0, "created_at": None, "preferences": default_preferences()}


def save_preferences(db, payload, settings):
    owner = authorize(db, payload, settings)
    digest = fingerprint(payload.model_dump(mode="json"))
    old = replay(db, Preference, "client_update_id", payload.client_update_id, owner, digest)
    if old:
        return preference_json(old)
    prefs = default_preferences()
    prefs.update(payload.model_dump(exclude={"participant_id", "client_update_id", "data_source", "consent"}))
    prefs["category_ratings"] = {**default_preferences()["category_ratings"], **payload.category_ratings}
    row = Preference(id=str(uuid4()), participant_id=owner.id, client_update_id=payload.client_update_id, request_hash=digest,
                     version=current_preferences(db, owner)["version"] + 1, created_at=now(), data_source=owner.data_source, payload=prefs)
    db.add(row)
    commit(db)
    return preference_json(row)


def context_references(db, payload, owner):
    refs = []
    for field, table in (("facial_session_id", FacialSession), ("voice_session_id", VoiceSession), ("risk_prediction_id", RiskPrediction)):
        ref_id = getattr(payload, field)
        if ref_id:
            row = owned(db, table, ref_id, owner)
            if row.data_source != owner.data_source:
                fail(409, "reference_source_mismatch", "Context records must have matching provenance.")
            refs.append({"kind": field, "record_id": row.id, "status": row.status, "used_for_ranking": False})
    return refs


def recommend(db, payload, settings):
    owner = authorize(db, payload, settings)
    digest = fingerprint(payload.model_dump(mode="json"))
    old = replay(db, Recommendation, "client_request_id", payload.client_request_id, owner, digest)
    if old:
        return old.result
    created = now()
    clock = datetime.fromisoformat(created)
    prefs = current_preferences(db, owner)
    feedback_rows = db.scalars(select(Feedback).where(Feedback.participant_id == owner.id, Feedback.data_source == owner.data_source,
                                                    Feedback.created_at <= created, Feedback.created_at >= (clock - timedelta(days=90)).isoformat(timespec="microseconds"))).all()
    feedback = feedback_summary([{"activity_id": r.activity_id, "helpfulness": r.helpfulness, "feedback_id": r.id, "created_at": r.created_at} for r in feedback_rows], clock)
    recent = db.scalars(select(ActivitySession).where(ActivitySession.participant_id == owner.id, ActivitySession.started_at <= created,
                                                      ActivitySession.started_at >= (clock - timedelta(days=RECENT_DAYS)).isoformat(timespec="microseconds"))).all()
    context = {"goal": payload.goal, "available_seconds": payload.available_seconds}
    candidates, excluded = rank(prefs["preferences"], context, payload.strategy, feedback, {r.activity_id for r in recent})
    refs = context_references(db, payload, owner)
    result = {"recommendation_id": str(uuid4()), "participant_id": owner.id, "data_source": owner.data_source,
              "client_request_id": payload.client_request_id, "created_at": created, "expires_at": (clock + timedelta(hours=24)).isoformat(timespec="microseconds"),
              "status": "offered" if candidates else "no_eligible_activity", "strategy": payload.strategy,
              "policy_version": POLICY_VERSION, "catalog_version": CATALOG_VERSION,
              "context": context, "references": refs, "preference_snapshot": prefs,
              "options": candidates[:payload.limit], "eligible_count": len(candidates), "excluded": excluded,
              "evidence": {"clinical_validation": False, "clinical_risk_used": False, "trained_model": False,
                           "score_semantics": "engineering_ranking_score_not_health_benefit_probability",
                           "logging_policy": "deterministic_ranking_user_selects_from_options", "action_propensity": None,
                           "feedback_scope": "same_participant_same_source_last90days_last20_per_activity",
                           "preference_defaulted": prefs["version"] == 0},
              "notice": NOTICE}
    db.add(Recommendation(id=result["recommendation_id"], participant_id=owner.id, client_request_id=payload.client_request_id,
                          request_hash=digest, created_at=created, data_source=owner.data_source, result=result))
    commit(db)
    return result


def session_json(row):
    elapsed = None if row.ended_at is None else max(0, (datetime.fromisoformat(row.ended_at) - datetime.fromisoformat(row.started_at)).total_seconds())
    return {"session_id": row.id, "participant_id": row.participant_id, "data_source": row.data_source,
            "recommendation_id": row.recommendation_id, "activity_id": row.activity_id, "status": row.status,
            "started_at": row.started_at, "ended_at": row.ended_at, "server_elapsed_seconds": elapsed,
            "activity": row.payload["activity"], "adherence_verified": False,
            "note": "Completion is a user-reported event. Elapsed wall time does not establish participation or health improvement."}


def start(db, payload, settings):
    owner = authorize(db, payload, settings)
    digest = fingerprint(payload.model_dump(mode="json"))
    old = replay(db, ActivitySession, "client_session_id", payload.client_session_id, owner, digest)
    if old:
        return old.start_result  # Frozen original response; GET session gives current state.
    rec = owned(db, Recommendation, payload.recommendation_id, owner)
    clock = datetime.now(timezone.utc)
    if clock > datetime.fromisoformat(rec.result["expires_at"]):
        fail(409, "recommendation_expired", "Request new options before starting an activity.")
    options = {r["activity"]["activity_id"]: r["activity"] for r in rec.result["options"]}
    if payload.activity_id not in options:
        fail(422, "activity_not_offered", "Choose an activity offered in this recommendation.")
    if db.scalar(select(ActivitySession).where(ActivitySession.recommendation_id == rec.id)):
        fail(409, "recommendation_already_used", "A recommendation can start one activity; request a new recommendation to continue.")
    if rec.result["catalog_version"] != CATALOG_VERSION:
        fail(409, "catalog_changed", "Request a new recommendation using the current catalog.")
    # A saved offer must never override a subsequently changed exclusion or access preference.
    current = current_preferences(db, owner)
    eligible, _ = rank(current["preferences"], rec.result["context"], "generic", {}, set())
    if payload.activity_id not in {r["activity"]["activity_id"] for r in eligible}:
        fail(409, "preferences_changed", "Current constraints exclude this activity. Request new options.")
    row = ActivitySession(id=str(uuid4()), participant_id=owner.id, recommendation_id=rec.id, client_session_id=payload.client_session_id,
                          request_hash=digest, activity_id=payload.activity_id, data_source=owner.data_source,
                          started_at=clock.isoformat(timespec="microseconds"), ended_at=None, status="started",
                          payload={"activity": options[payload.activity_id], "start_preference_version": current["version"]}, start_result={})
    row.start_result = session_json(row)
    db.add(row)
    commit(db)
    return row.start_result


def finish(db, payload, settings):
    owner = authorize(db, payload, settings)
    digest = fingerprint(payload.model_dump(mode="json"))
    old = replay(db, Event, "client_event_id", payload.client_event_id, owner, digest)
    if old:
        return old.result
    row = owned(db, ActivitySession, payload.session_id, owner)
    ended = now()
    # Conditional update prevents two concurrent terminal outcomes from both succeeding.
    changed = db.execute(update(ActivitySession).where(ActivitySession.id == row.id, ActivitySession.status == "started").values(status=payload.outcome, ended_at=ended))
    if changed.rowcount != 1:
        db.rollback()
        fail(409, "session_already_finished", "A session has one terminal outcome. Retry its original event to recover the response.")
    db.flush()
    db.refresh(row)
    result = {"event_id": str(uuid4()), "created_at": ended, "session": session_json(row)}
    db.add(Event(id=result["event_id"], participant_id=owner.id, session_id=row.id, client_event_id=payload.client_event_id,
                 request_hash=digest, created_at=ended, result=result))
    commit(db)
    return result


def feedback(db, payload, settings):
    owner = authorize(db, payload, settings)
    digest = fingerprint(payload.model_dump(mode="json"))
    old = replay(db, Feedback, "client_feedback_id", payload.client_feedback_id, owner, digest)
    if old:
        return old.result
    row = owned(db, ActivitySession, payload.session_id, owner)
    if row.status != "completed":
        fail(409, "completed_session_required", "Only completed sessions can receive helpfulness feedback; abandoned sessions remain engagement events.")
    if db.scalar(select(Feedback).where(Feedback.session_id == row.id)):
        fail(409, "feedback_already_recorded", "One immutable rating is allowed per completed session.")
    result = {"feedback_id": str(uuid4()), "participant_id": owner.id, "session_id": row.id, "activity_id": row.activity_id,
              "data_source": owner.data_source, "created_at": now(), "helpfulness": payload.helpfulness,
              "would_repeat": payload.would_repeat, "normalized_helpfulness": (payload.helpfulness - 1) / 4,
              "clinical_outcome": False}
    db.add(Feedback(id=result["feedback_id"], participant_id=owner.id, session_id=row.id, client_feedback_id=payload.client_feedback_id,
                    request_hash=digest, created_at=result["created_at"], data_source=owner.data_source, activity_id=row.activity_id,
                    helpfulness=payload.helpfulness, would_repeat=int(payload.would_repeat), result=result))
    commit(db)
    return result


def metrics(db, owner):
    recommendations = db.scalars(select(Recommendation).where(Recommendation.participant_id == owner.id)).all()
    sessions = db.scalars(select(ActivitySession).where(ActivitySession.participant_id == owner.id)).all()
    ratings = db.scalars(select(Feedback).where(Feedback.participant_id == owner.id)).all()
    out = []
    for strategy in ("generic", "preference", "adaptive"):
        offers = [r for r in recommendations if r.result["strategy"] == strategy and r.result["status"] == "offered"]
        ids = {r.id for r in offers}
        started = [s for s in sessions if s.recommendation_id in ids]
        completed = [s for s in started if s.status == "completed"]
        abandoned = [s for s in started if s.status == "abandoned"]
        session_ids = {s.id for s in started}
        feedbacks = [f for f in ratings if f.session_id in session_ids]
        out.append({"strategy": strategy, "offered_recommendations": len(offers), "started_sessions": len(started),
                    "completed_sessions": len(completed), "abandoned_sessions": len(abandoned),
                    "unfinished_sessions": sum(s.status == "started" for s in started), "feedback_count": len(feedbacks),
                    "start_rate": len(started) / len(offers) if offers else None,
                    "completion_rate_among_started": len(completed) / len(started) if started else None,
                    "feedback_response_rate_among_completed": len(feedbacks) / len(completed) if completed else None,
                    "mean_helpfulness_among_responders": sum(f.helpfulness for f in feedbacks) / len(feedbacks) if feedbacks else None,
                    "would_repeat_fraction_among_responders": sum(bool(f.would_repeat) for f in feedbacks) / len(feedbacks) if feedbacks else None})
    return {"participant_id": owner.id, "data_source": owner.data_source, "strategies": out,
            "causal_policy_comparison": False, "clinical_effectiveness": False,
            "note": "Descriptive counts only. Nonresponse is missing, not a zero rating. User choices, unmatched contexts and deterministic ranking confound comparisons."}
