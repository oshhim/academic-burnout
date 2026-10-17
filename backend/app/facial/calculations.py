"""Deterministic measurements. No stress/burnout classifier is hidden here."""
from collections import Counter

import numpy as np

from app.schemas import QualityResult, SessionInput, Window

FEATURES = ("eye_aspect_ratio", "brow_lowering", "lip_press", "jaw_open", "head_motion_deg")
# Engineering floors prevent division by zero/unstable scores. Not clinical limits.
SCALE_FLOORS = dict(zip(FEATURES, (0.025, 0.025, 0.025, 0.025, 1.0)))
MODEL_VERSION = "c1-statistical-v1.0.0"
WARNING = "Visual deviation is not evidence of stress, burnout, fatigue or psychological recovery."


def window_reasons(window: Window):
    q = window.quality
    reasons = []
    for bad, reason in (
        (q.face_count != 1, "require_exactly_one_face"),
        (q.tracking_score < 0.6, "low_tracking_score"),
        (q.brightness < 0.15 or q.brightness > 0.95, "poor_brightness"),
        (q.sharpness < 0.35, "low_sharpness"),
        (abs(q.yaw_deg) > 35 or abs(q.pitch_deg) > 30, "excessive_head_pose"),
    ):
        if bad:
            reasons.append(reason)
    return reasons


def inspect_quality(payload: SessionInput):
    valid = []
    reasons = Counter()
    for w in payload.windows:
        failures = window_reasons(w)
        if failures:
            reasons.update(failures)
        else:
            valid.append(w)
    elapsed = payload.windows[-1].t_start_sec + payload.windows[-1].duration_sec
    usable = sum(w.duration_sec for w in valid)
    fraction = usable / elapsed
    if usable < 8:
        reasons.update(["less_than_8_usable_seconds"])
    if fraction < 0.8:
        reasons.update(["less_than_80_percent_usable_coverage"])
    accepted = usable >= 8 and fraction >= 0.8
    score = fraction * (sum(w.quality.tracking_score * w.duration_sec for w in valid) / usable if usable else 0)
    result = QualityResult(
        status="accepted" if accepted else "insufficient_quality",
        usable_duration_sec=round(usable, 6), elapsed_duration_sec=round(elapsed, 6),
        usable_fraction=round(fraction, 6), quality_score=round(score, 6),
        rejected_window_count=len(payload.windows) - len(valid), reasons=sorted(reasons),
    )
    return result, valid


def aggregate(windows: list[Window]):
    weights = np.array([w.duration_sec for w in windows])
    return {f: float(np.average([getattr(w.features, f) for w in windows], weights=weights)) for f in FEATURES}


def calculate_baseline(sessions: list[dict]):
    matrix = np.array([[s[f] for f in FEATURES] for s in sessions])
    centers = np.median(matrix, axis=0)
    robust_scales = 1.4826 * np.median(np.abs(matrix - centers), axis=0)
    scales = np.maximum(robust_scales, list(SCALE_FLOORS.values()))
    return dict(zip(FEATURES, centers.tolist())), dict(zip(FEATURES, scales.tolist()))


def deviation(features, center, scale):
    signed = {f: (features[f] - center[f]) / scale[f] for f in FEATURES}
    score = float(np.mean(np.abs(list(signed.values()))))
    level = "within_reference_range" if score < 1 else "moderate_visual_change" if score < 2 else "large_visual_change"
    return {
        "mean_absolute_standardized_deviation": round(score, 6),
        "level": level,
        "per_feature_signed_z": {f: round(z, 6) for f, z in signed.items()},
        "top_changed_features": sorted(FEATURES, key=lambda f: abs(signed[f]), reverse=True)[:3],
    }


def temporal_measurements(valid, payload, center, scale):
    groups = {phase: [w for w in valid if w.phase == phase] for phase in ("neutral", "task", "recovery")}
    scores = {phase: deviation(aggregate(ws), center, scale)["mean_absolute_standardized_deviation"] for phase, ws in groups.items() if ws}
    result = {
        "status": "not_measurable", "reason": None, "phase_deviations": scores,
        "task_to_recovery_change": None, "return_fraction": None, "return_rate_z_per_sec": None,
        "interpretation": "No psychological recovery inference is made.",
    }
    if payload.protocol != "neutral_task_recovery":
        result["reason"] = "neutral_only_protocol"
        return result
    if any(sum(w.duration_sec for w in groups[p]) < 5 for p in groups):
        result["reason"] = "each_phase_requires_at_least_5_usable_seconds"
        return result
    if scores["task"] <= scores["neutral"] + 0.25:
        result["reason"] = "no_observed_task_increase_over_neutral"
        return result
    if scores["task"] < 0.5:
        result["reason"] = "task_deviation_too_small_for_stable_fraction"
        return result
    def midpoint(ws):
        return sum((w.t_start_sec + w.duration_sec / 2) * w.duration_sec for w in ws) / sum(w.duration_sec for w in ws)
    interval = midpoint(groups["recovery"]) - midpoint(groups["task"])
    change = scores["task"] - scores["recovery"]
    result.update(
        status="measured", task_to_recovery_change=round(change, 6),
        return_fraction=round(change / scores["task"], 6),
        return_rate_z_per_sec=round(change / interval, 6),
        interpretation="positive: closer to baseline; negative: farther from baseline. This is a visual measurement only.",
    )
    return result
