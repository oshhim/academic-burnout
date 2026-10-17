"""Pure deterministic ranking shared by API, tests and simulation. No clinical model."""
from collections import defaultdict
from datetime import datetime, timedelta
from app.interventions.catalog import ACTIVITIES, POLICY_VERSION

PRIOR_COUNT = 3
FEEDBACK_WINDOW_DAYS = 90
RECENT_DAYS = 7
RECENT_PENALTY = 0.05


def feedback_summary(records, as_of):
    groups = defaultdict(list)
    for record in records:
        when = datetime.fromisoformat(record["created_at"])
        if as_of - timedelta(days=FEEDBACK_WINDOW_DAYS) <= when <= as_of:
            groups[record["activity_id"]].append((when, record["feedback_id"], record["helpfulness"]))
    # Bound history: last 20 rated sessions per activity, avoiding unlimited old evidence.
    return {activity: {"count": len(rows[-20:]), "sum": sum((r[2] - 1) / 4 for r in rows[-20:]), "feedback_ids": [r[1] for r in rows[-20:]]}
            for activity, original in groups.items() for rows in [sorted(original)]}


def rank(preferences, context, strategy, feedback, recent_activity_ids):
    candidates, excluded = [], []
    for activity in ACTIVITIES:
        aid = activity["activity_id"]
        reasons = []
        if aid in preferences["excluded_activity_ids"]:
            reasons.append("explicitly_excluded")
        if activity["duration_seconds"] > min(preferences["max_duration_seconds"], context["available_seconds"]):
            reasons.append("exceeds_available_time")
        if activity["movement"] and not preferences["allow_movement"]:
            reasons.append("movement_disabled")
        if activity["audio"] and not preferences["allow_audio"]:
            reasons.append("audio_disabled")
        if reasons:
            excluded.append({"activity_id": aid, "reasons": reasons})
            continue
        goal_match = float(context["goal"] in activity["goals"])
        # A small duration fit term prevents assuming longer always means better.
        duration_fit = 1 - activity["duration_seconds"] / context["available_seconds"]
        base = 0.7 * goal_match + 0.3 * duration_fit
        preference = (preferences["category_ratings"].get(activity["category"], 3) - 1) / 4
        history = feedback.get(aid, {"count": 0, "sum": 0, "feedback_ids": []})
        posterior = (PRIOR_COUNT * 0.5 + history["sum"]) / (PRIOR_COUNT + history["count"])
        penalty = RECENT_PENALTY if aid in recent_activity_ids and strategy == "adaptive" else 0.0
        score = {"generic": base, "preference": 0.55 * base + 0.45 * preference,
                 "adaptive": 0.55 * base + 0.25 * preference + 0.20 * posterior - penalty}[strategy]
        candidates.append({"activity": dict(activity), "score": round(score, 8),
                           "explanation": {"goal_match": goal_match, "duration_fit": round(duration_fit, 8), "category_preference": preference,
                                           "feedback_posterior": round(posterior, 8), "feedback_count": history["count"],
                                           "feedback_used": strategy == "adaptive", "preference_used": strategy != "generic",
                                           "recent_repeat_penalty": penalty, "feedback_ids": history["feedback_ids"] if strategy == "adaptive" else []}})
    candidates.sort(key=lambda row: (-row["score"], row["activity"]["activity_id"]))
    return candidates, excluded


def status():
    return {"status": "implemented", "method": "deterministic_preference_and_feedback_ranking", "version": POLICY_VERSION,
            "trained_model": False, "contextual_bandit": False, "clinical_validation": False,
            "weight_status": "provisional_engineering_settings", "strategies": ["generic", "preference", "adaptive"]}
