from datetime import datetime, timedelta, timezone
import math
import random
from app.interventions.catalog import BY_ID, CATEGORIES
from app.interventions.policy import feedback_summary, rank
from app.interventions.schemas import default_preferences
from training.evaluate_interventions import simulate


def context(goal="refocus", seconds=300):
    return {"goal": goal, "available_seconds": seconds}


def test_independent_constraint_audit_for_all_policies():
    rng = random.Random(711)
    for _ in range(100):
        prefs = default_preferences()
        prefs.update(allow_audio=rng.choice([True, False]), allow_movement=rng.choice([True, False]), max_duration_seconds=rng.choice([60, 120, 180, 300]))
        prefs["excluded_activity_ids"] = rng.sample(list(BY_ID), rng.randint(0, 6))
        ctx = context(seconds=rng.choice([60, 90, 120, 180, 300, 600]))
        for strategy in ("generic", "preference", "adaptive"):
            options, _ = rank(prefs, ctx, strategy, {}, set())
            for option in options:
                activity = option["activity"]
                assert activity["activity_id"] not in prefs["excluded_activity_ids"]
                assert activity["duration_seconds"] <= min(ctx["available_seconds"], prefs["max_duration_seconds"])
                assert prefs["allow_movement"] or not activity["movement"]
                assert prefs["allow_audio"] or not activity["audio"]
                assert math.isfinite(option["score"])


def test_generic_ignores_likes_and_feedback_while_preference_responds():
    neutral = default_preferences()
    preferred = default_preferences()
    preferred["category_ratings"].update(pause=1, planning=5)
    a, _ = rank(neutral, context(), "generic", {}, set())
    b, _ = rank(preferred, context(), "generic", {"quiet_pause": {"count": 100, "sum": 0, "feedback_ids": []}}, {"quiet_pause"})
    assert [(r["activity"]["activity_id"], r["score"]) for r in a] == [(r["activity"]["activity_id"], r["score"]) for r in b]
    p, _ = rank(preferred, context(), "preference", {}, set())
    assert a[0]["activity"]["activity_id"] == "quiet_pause"
    assert p[0]["activity"]["activity_id"] == "next_small_step"


def test_feedback_prior_repetition_and_nonresponsive_missing():
    prefs = default_preferences()
    options, _ = rank(prefs, context(), "adaptive", {}, set())
    before = next(x for x in options if x["activity"]["activity_id"] == "quiet_pause")
    assert before["explanation"]["feedback_posterior"] == 0.5
    options, _ = rank(prefs, context(), "adaptive", {"quiet_pause": {"count": 1, "sum": 0, "feedback_ids": ["f1"]}}, {"quiet_pause"})
    after = next(x for x in options if x["activity"]["activity_id"] == "quiet_pause")
    assert after["explanation"]["feedback_posterior"] == 0.375
    assert abs(before["score"] - after["score"] - 0.075) < 1e-8
    assert after["explanation"]["feedback_ids"] == ["f1"]


def test_feedback_temporal_cutoff_expiry_and_last20():
    clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def item(key, when, rating=5):
        return {"feedback_id": key, "activity_id": "quiet_pause", "created_at": when.isoformat(), "helpfulness": rating}
    rows = [item(str(i), clock - timedelta(days=i)) for i in range(21)]
    rows += [item("future", clock + timedelta(seconds=1)), item("too-old", clock - timedelta(days=91))]
    stats = feedback_summary(rows, clock)["quiet_pause"]
    assert stats["count"] == 20 and stats["sum"] == 20
    assert set(stats["feedback_ids"]) == {str(i) for i in range(20)}


def test_simulator_reproducible_separate_from_human_evaluation():
    first, logs = simulate(people=3, rounds=7, seed=10)
    second, replay = simulate(people=3, rounds=7, seed=10)
    assert first == second and logs == replay
    assert first["synthetic_only"] and first["human_participants"] == 0
    assert not first["clinical_validation"] and not first["real_world_off_policy_evaluation"]
    assert all(row["hard_constraint_violations"] == 0 for row in first["strategy_comparison"])
    assert all(row["data_source"] == "synthetic_demo" for row in logs)
