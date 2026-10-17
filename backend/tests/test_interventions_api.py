from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from scripts.run_interventions_demo import run_interventions_demo
from app.models import (Participant, InterventionPreference, InterventionRecommendation, InterventionSession, InterventionEvent, InterventionFeedback)


def base(pid="I1", source="synthetic_demo", consent=True):
    return {"participant_id": pid, "data_source": source, "consent": consent}


def register(client, pid="I1"):
    response = client.post("/api/v1/participants", json=base(pid))
    assert response.status_code == 201


def prefs(client, pid="I1", update_id="pref-1", **changes):
    return client.post("/api/v1/interventions/preferences", json={**base(pid), "client_update_id": update_id, **changes})


def rec(client, pid="I1", request_id="rec-1", **changes):
    return client.post("/api/v1/interventions/recommendations", json={**base(pid), "client_request_id": request_id, "goal": "refocus", "available_seconds": 300, **changes})


def start(client, recommendation, pid="I1", client_id="start-1", activity_id=None):
    return client.post("/api/v1/interventions/sessions", json={**base(pid), "client_session_id": client_id, "recommendation_id": recommendation["recommendation_id"], "activity_id": activity_id or recommendation["options"][0]["activity"]["activity_id"]})


def finish(client, session_id, event_id="end-1", outcome="completed", pid="I1"):
    return client.post("/api/v1/interventions/events", json={**base(pid), "client_event_id": event_id, "session_id": session_id, "outcome": outcome})


def rate(client, session_id, client_id="fb-1", pid="I1", helpfulness=5):
    return client.post("/api/v1/interventions/feedback", json={**base(pid), "client_feedback_id": client_id, "session_id": session_id, "helpfulness": helpfulness, "would_repeat": True})


def test_full_demo_and_registry(client):
    report = run_interventions_demo(client)
    assert report["comparison"]["generic"]["options"][0]["activity"]["activity_id"] == "quiet_pause"
    assert report["comparison"]["preference"]["options"][0]["activity"]["activity_id"] == "next_small_step"
    assert report["current_session"]["status"] == "completed"
    assert report["current_session"]["adherence_verified"] is False
    assert client.get("/interventions-demo").status_code == 200
    assert client.get("/api/v1/models").json()["interventions"]["clinical_validation"] is False
    assert client.get("/api/v1/interventions/evaluation").json()["synthetic_only"] is True


def test_defaults_no_history_and_empty_recommendation(client):
    register(client)
    r = rec(client).json()
    assert r["status"] == "offered" and r["evidence"]["preference_defaulted"]
    assert r["preference_snapshot"]["version"] == 0
    assert r["options"][0]["explanation"]["feedback_count"] == 0
    assert r["evidence"]["action_propensity"] is None
    empty = rec(client, request_id="empty", available_seconds=60).json()
    assert empty["status"] == "no_eligible_activity" and empty["options"] == []
    metrics = client.get("/api/v1/interventions/metrics/I1").json()
    assert all(s["mean_helpfulness_among_responders"] is None for s in metrics["strategies"])


def test_preference_versions_idempotency_and_recommendation_snapshot(client):
    register(client)
    first = prefs(client, category_ratings={"planning": 5}).json()
    assert prefs(client, category_ratings={"planning": 5}).json() == first
    assert prefs(client, category_ratings={"planning": 1}).status_code == 409
    original = rec(client).json()
    second = prefs(client, update_id="pref-2", category_ratings={"planning": 1}).json()
    assert second["version"] == 2 and second["preferences"]["category_ratings"]["pause"] == 3
    assert rec(client).json() == original
    assert rec(client, goal="organize").status_code == 409
    current = client.get("/api/v1/interventions/preferences/I1").json()
    assert current == second
    assert client.get("/api/v1/interventions/history/I1?kind=preferences&limit=1").json()["total"] == 2


def test_lifecycle_single_activity_terminal_event_and_feedback(client):
    register(client)
    recommendation = rec(client).json()
    started = start(client, recommendation).json()
    assert start(client, recommendation).json() == started
    assert start(client, recommendation, client_id="another").status_code == 409
    assert rate(client, started["session_id"]).status_code == 409
    terminal = finish(client, started["session_id"]).json()
    assert finish(client, started["session_id"]).json() == terminal
    assert finish(client, started["session_id"], event_id="again").status_code == 409
    assert finish(client, started["session_id"], outcome="abandoned").status_code == 409
    rating = rate(client, started["session_id"]).json()
    assert rate(client, started["session_id"]).json() == rating
    assert rate(client, started["session_id"], client_id="fb-2").status_code == 409
    assert rate(client, started["session_id"], helpfulness=1).status_code == 409
    # A retried start returns the immutable initial response; GET returns terminal state.
    assert start(client, recommendation).json() == started
    assert client.get("/api/v1/interventions/sessions/I1/" + started["session_id"]).json()["status"] == "completed"
    metrics = client.get("/api/v1/interventions/metrics/I1").json()["strategies"][2]
    assert metrics["feedback_count"] == 1 and metrics["completed_sessions"] == 1


def test_abandonment_is_engagement_not_negative_rating(client):
    register(client)
    started = start(client, rec(client).json()).json()
    assert finish(client, started["session_id"], outcome="abandoned").status_code == 201
    assert rate(client, started["session_id"]).status_code == 409
    result = rec(client, request_id="next").json()
    assert all(option["explanation"]["feedback_count"] == 0 for option in result["options"])
    metrics = client.get("/api/v1/interventions/metrics/I1").json()["strategies"][2]
    assert metrics["abandoned_sessions"] == 1 and metrics["mean_helpfulness_among_responders"] is None


def test_exclusion_rechecked_before_start_and_offered_option_enforced(client):
    register(client)
    offer = rec(client, limit=1).json()
    assert start(client, offer, activity_id="not-an-activity").status_code == 422
    aid = offer["options"][0]["activity"]["activity_id"]
    assert prefs(client, excluded_activity_ids=[aid]).status_code == 201
    assert start(client, offer).status_code == 409
    new = rec(client, request_id="new").json()
    assert aid not in [o["activity"]["activity_id"] for o in new["options"]]


def test_offer_expiry_is_enforced(client):
    register(client)
    offer = rec(client).json()
    with client.app.state.sessions() as db:
        row = db.get(InterventionRecommendation, offer["recommendation_id"])
        row.result = {**row.result, "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}
        db.commit()
    assert start(client, offer).json()["error"]["code"] == "recommendation_expired"


def test_participant_and_context_ownership(client):
    register(client)
    register(client, "I2")
    offer = rec(client).json()
    assert start(client, offer, pid="I2").status_code == 404
    started = start(client, offer).json()
    assert finish(client, started["session_id"], pid="I2").status_code == 404
    assert rate(client, started["session_id"], pid="I2").status_code == 404
    assert client.get("/api/v1/interventions/sessions/I2/" + started["session_id"]).status_code == 404
    assert rec(client, request_id="badref", risk_prediction_id="absent").status_code == 404
    from scripts.risk_demo_data import demo_observations
    daily, weekly = demo_observations("I1", "steady")
    assert client.post("/api/v1/risk/daily/batch", json={"records": daily}).status_code == 201
    for r in weekly:
        assert client.post("/api/v1/risk/weekly", json=r).status_code == 201
    prediction = client.post("/api/v1/risk/predictions", json={"participant_id": "I1", "client_prediction_id": "context"}).json()
    unlinked = rec(client, request_id="unlinked-current").json()
    linked = rec(client, request_id="linked", risk_prediction_id=prediction["prediction_id"]).json()
    assert linked["references"][0]["used_for_ranking"] is False
    assert [(o["activity"]["activity_id"], o["score"]) for o in linked["options"]] == [(o["activity"]["activity_id"], o["score"]) for o in unlinked["options"]]
    assert rec(client, pid="I2", request_id="crossref", risk_prediction_id=prediction["prediction_id"]).status_code == 404


def test_validation_consent_source_and_auth(client):
    register(client)
    assert prefs(client, category_ratings={"pause": True}).status_code == 422
    assert prefs(client, category_ratings={"pause": "5"}).status_code == 422
    assert prefs(client, category_ratings={"unknown": 5}).status_code == 422
    assert prefs(client, excluded_activity_ids=["quiet_pause", "quiet_pause"]).status_code == 422
    assert prefs(client, allow_audio="false").status_code == 422
    assert rec(client, available_seconds=True).status_code == 422
    assert rec(client, strategy="bandit").status_code == 422
    assert rec(client, consent=False).status_code == 403
    assert rec(client, data_source="local_research").status_code == 409
    assert rec(client, data_source="public_dataset").status_code == 422
    assert rec(client, clinical_risk_probability=0.9).status_code == 422
    assert rec(client, created_at="2020-01-01T00:00:00Z").status_code == 422
    client.headers["X-API-Key"] = "incorrect"
    assert client.get("/api/v1/interventions/catalog").status_code == 401


def test_local_source_research_gate_and_feedback_separation(client):
    register(client)
    sid = start(client, rec(client).json()).json()["session_id"]
    finish(client, sid)
    rate(client, sid)
    with client.app.state.sessions() as db:
        db.add(Participant(id="LOCAL", data_source="local_research", created_at=datetime.now(timezone.utc).isoformat(), consent_version="approved-pilot-v1"))
        db.commit()
    body = {**base("LOCAL", "local_research"), "client_request_id": "local-1", "goal": "rest", "available_seconds": 300}
    assert client.post("/api/v1/interventions/recommendations", json=body).status_code == 403
    client.app.state.settings.enable_research_mode = True
    result = client.post("/api/v1/interventions/recommendations", json=body)
    assert result.status_code == 201
    assert result.json()["data_source"] == "local_research"
    assert all(o["explanation"]["feedback_count"] == 0 for o in result.json()["options"])
    assert prefs(client, pid="LOCAL", data_source="local_research").status_code == 201
    client.app.state.settings.enable_research_mode = False
    assert prefs(client, pid="LOCAL", update_id="later", data_source="local_research").status_code == 403
    # Export remains available when research writes are disabled.
    assert client.get("/api/v1/participants/LOCAL/export").status_code == 200


def test_complete_export_deletion_scoped_and_no_orphans(client):
    register(client)
    register(client, "KEEP")
    prefs(client)
    sid = start(client, rec(client).json()).json()["session_id"]
    finish(client, sid)
    rate(client, sid)
    export = client.get("/api/v1/participants/I1/export").json()
    for kind in ("preferences", "recommendations", "sessions", "events", "feedback"):
        assert len(export["intervention_" + kind]) == 1
        assert client.get("/api/v1/interventions/history/I1?kind=" + kind).json()["total"] == 1
    assert client.delete("/api/v1/participants/I1").status_code == 204
    assert client.get("/api/v1/interventions/history/I1").status_code == 404
    assert client.get("/api/v1/participants/KEEP/export").status_code == 200
    with client.app.state.sessions() as db:
        for table in (InterventionPreference, InterventionRecommendation, InterventionSession, InterventionEvent, InterventionFeedback):
            assert db.scalar(select(table).where(table.participant_id == "I1")) is None


def test_completed_but_unrated_does_not_change_feedback_posterior(client):
    register(client)
    first = rec(client).json()
    started = start(client, first).json()
    finish(client, started["session_id"])
    after = rec(client, request_id="unrated-next").json()
    assert all(o["explanation"]["feedback_count"] == 0 and o["explanation"]["feedback_posterior"] == 0.5 for o in after["options"])
    metrics = client.get("/api/v1/interventions/metrics/I1").json()["strategies"][2]
    assert metrics["feedback_response_rate_among_completed"] == 0
    assert metrics["mean_helpfulness_among_responders"] is None


def test_recommendation_and_feedback_readback_are_frozen(client):
    register(client)
    first = rec(client).json()
    sid = start(client, first).json()["session_id"]
    finish(client, sid)
    rate(client, sid, helpfulness=1)
    assert rec(client).json() == first
    assert client.get("/api/v1/interventions/recommendations/I1/" + first["recommendation_id"]).json() == first
    later = rec(client, request_id="later-after-rating").json()
    chosen = next(o for o in later["options"] if o["activity"]["activity_id"] == first["options"][0]["activity"]["activity_id"])
    assert chosen["explanation"]["feedback_count"] == 1
    assert chosen["explanation"]["feedback_posterior"] == 0.375
