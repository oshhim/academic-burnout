"""End-to-end synthetic preference -> offer -> session -> feedback demonstration."""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4
import httpx


def run_interventions_demo(client):
    def post(path, body):
        response = client.post("/api/v1/" + path, json=body)
        response.raise_for_status()
        return response.json()
    pid = "C4-DEMO-" + uuid4().hex[:8]
    base = {"participant_id": pid, "data_source": "synthetic_demo", "consent": True}
    post("participants", base)
    prefs = post("interventions/preferences", {**base, "client_update_id": "prefs-v1", "category_ratings": {"planning": 5, "pause": 2, "movement": 1, "reflection": 4, "audio": 1}, "allow_audio": False, "allow_movement": False})
    comparison = {}
    for strategy in ("generic", "preference", "adaptive"):
        comparison[strategy] = post("interventions/recommendations", {**base, "client_request_id": "initial-" + strategy, "strategy": strategy, "goal": "refocus", "available_seconds": 300})
    rec = comparison["adaptive"]
    start_body = {**base, "client_session_id": "activity-1", "recommendation_id": rec["recommendation_id"], "activity_id": rec["options"][0]["activity"]["activity_id"]}
    started = post("interventions/sessions", start_body)
    terminal = post("interventions/events", {**base, "client_event_id": "finish-1", "session_id": started["session_id"], "outcome": "completed"})
    rated = post("interventions/feedback", {**base, "client_feedback_id": "rating-1", "session_id": started["session_id"], "helpfulness": 1, "would_repeat": False})
    after = post("interventions/recommendations", {**base, "client_request_id": "after-feedback", "strategy": "adaptive", "goal": "refocus", "available_seconds": 300})
    # Changed rating and recent-start diversity both affect the next frozen explanation.
    before = next(o for o in rec["options"] if o["activity"]["activity_id"] == started["activity_id"])
    after_option = next(o for o in after["options"] if o["activity"]["activity_id"] == started["activity_id"])
    assert after_option["explanation"]["feedback_count"] == 1
    assert after_option["score"] < before["score"]
    current = client.get("/api/v1/interventions/sessions/" + pid + "/" + started["session_id"])
    current.raise_for_status()
    metrics = client.get("/api/v1/interventions/metrics/" + pid)
    metrics.raise_for_status()
    return {"data_source": "synthetic_demo", "participant_id": pid, "preferences": prefs,
            "comparison": comparison, "started": started, "terminal": terminal, "feedback": rated, "after_feedback": after,
            "current_session": current.json(), "metrics": metrics.json(), "warning": "Constructed software scenario with a simulated rating; completion and elapsed time are not adherence or benefit evidence."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", "local-demo-key-change-me"))
    parser.add_argument("--output", type=Path, default=Path("data/interventions_demo_results.json"))
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, headers={"X-API-Key": args.api_key}, timeout=60, trust_env=False) as client:
        result = run_interventions_demo(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for strategy, rec in result["comparison"].items():
        print(strategy, "->", rec["options"][0]["activity"]["title"])
    print("PASS: synthetic preference, recommendation, completion, feedback and adaptation workflow.")
    print("Saved:", args.output)
