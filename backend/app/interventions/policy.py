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


def rank(preferences, context, strategy, feedback, recent_activity_ids, integration=None):
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
        adaptive = strategy in {"adaptive", "multimodal_weighted"}
        penalty = RECENT_PENALTY if aid in recent_activity_ids and adaptive else 0.0
        independent = .55 * base + .25 * preference + .20 * posterior
        contributions = {}
        share = 0.0
        if strategy == "multimodal_weighted" and integration and not integration["fallback"]:
            share = integration["context_share"]
            for kind, item in integration["modalities"].items():
                if item["available"]:
                    compatibility = item["compatibility_by_category"][activity["category"]]
                    contributions[kind] = {"compatibility": compatibility, "normalized_weight": item["normalized_weight"],
                                           "weighted_compatibility": item["normalized_weight"] * compatibility,
                                           "final_score_contribution": share * item["normalized_weight"] * compatibility}
        multimodal = sum(c["weighted_compatibility"] for c in contributions.values()) if contributions else None
        weighted = (1 - share) * independent + share * (multimodal or 0.0) - penalty
        score = {"generic": base, "preference": 0.55 * base + 0.45 * preference,
                 "adaptive": independent - penalty, "multimodal_weighted": weighted}[strategy]
        candidates.append({"activity": dict(activity), "score": round(score, 8),
                           "explanation": {"goal_match": goal_match, "duration_fit": round(duration_fit, 8), "category_preference": preference,
                                           "feedback_posterior": round(posterior, 8), "feedback_count": history["count"],
                                           "feedback_used": adaptive, "preference_used": strategy != "generic",
                                           "recent_repeat_penalty": penalty, "feedback_ids": history["feedback_ids"] if adaptive else [],
                                           "independent_score_before_penalty": round(independent, 8),
                                           "context_share": share, "context_score": multimodal,
                                           "component_contributions": contributions,
                                           "independent_final_contribution": (1 - share) * independent}})
    candidates.sort(key=lambda row: (-row["score"], row["activity"]["activity_id"]))
    return candidates, excluded


def status():
    return {"status": "implemented", "method": "optional_availability_weighted_preference_feedback_ranking", "version": POLICY_VERSION,
            "trained_model": False, "contextual_bandit": False, "clinical_validation": False,
            "weight_status": "provisional_engineering_settings", "strategies": ["generic", "preference", "adaptive", "multimodal_weighted"],
            "optional_component_context": True, "context_mapping_scope": "synthetic_demo_only"}
