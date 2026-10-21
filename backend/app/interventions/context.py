"""Read-only adapters from C1–C3 outputs into C4's synthetic research policy.

This module never calls, trains or changes the other components. An absent,
stale, rejected or incompatible assessment contributes exactly zero weight.
The compatibility mappings are test hypotheses, not measured activity benefit.
"""
from datetime import datetime, timedelta, timezone
import math

from sqlalchemy import select

from app.facial.service import fail
from app.models import FacialBaseline, FacialSession, VoiceSession, RiskPrediction, InterventionDemoContext

MAPPING_VERSION = "synthetic-compatibility-v1"
BASE_WEIGHTS = {"facial": 0.30, "voice": 0.20, "risk": 0.50}
CONTEXT_SHARE = 0.25
MAX_AGE_SECONDS = {"facial": 1800, "voice": 1800, "risk": 86400}
CATEGORIES = ("pause", "movement", "planning", "reflection", "audio")
COMPATIBILITY = {
    "persistent_visual_change": dict(zip(CATEGORIES, (.8, .5, .2, .5, .5))),
    "returned_or_stable_visual": dict.fromkeys(CATEGORIES, .5),
    "sad_style_fixture": dict(zip(CATEGORIES, (.7, .5, .4, .6, .6))),
    "other_style_fixture": dict.fromkeys(CATEGORIES, .5),
    "higher_exhaustion_proxy": dict(zip(CATEGORIES, (.7, .5, .3, .5, .5))),
    "lower_exhaustion_proxy": dict.fromkeys(CATEGORIES, .5),
}
TABLES = {"facial": (FacialSession, "facial_session_id"), "voice": (VoiceSession, "voice_session_id"), "risk": (RiskPrediction, "risk_prediction_id")}


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def instant(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    return dt.astimezone(timezone.utc)


def unavailable(kind, reason="not_completed", **extra):
    return {"component": kind, "available": False, "reason": reason, "record_id": None,
            "origin": "assessment_record", "reliability": 0.0, "normalized_weight": 0.0, **extra}


def mapped(kind, row_id, when, label, origin="assessment_record"):
    return {"component": kind, "available": True, "reason": "eligible", "record_id": row_id,
            "recorded_at": when, "origin": origin, "mapping_key": label,
            "compatibility_by_category": dict(COMPATIBILITY[label]),
            # Binary technical gate only. This is not classifier confidence.
            "reliability": 1.0, "normalized_weight": 0.0}


def normalize(modalities, clock, mode, demo_context_id=None):
    total = sum(BASE_WEIGHTS[k] * m["reliability"] for k, m in modalities.items() if m["available"])
    for kind, m in modalities.items():
        m["normalized_weight"] = BASE_WEIGHTS[kind] * m["reliability"] / total if total and m["available"] else 0.0
    return {"mapping_version": MAPPING_VERSION, "as_of": clock.isoformat(timespec="microseconds"),
            "context_mode": mode, "demo_context_id": demo_context_id, "base_weights": dict(BASE_WEIGHTS),
            "normalized_weights": {k: m["normalized_weight"] for k, m in modalities.items()},
            "context_share": CONTEXT_SHARE if total else 0.0, "fallback": not bool(total),
            "fallback_reason": None if total else "no_eligible_component_results",
            "modalities": modalities, "synthetic_mapping_only": True,
            "weights_learned": False, "clinical_validation": False}


def owned_reference(db, table, ref_id, owner):
    row = db.get(table, ref_id)
    if row is None or row.participant_id != owner.id:
        fail(404, "record_not_found", "The context record does not belong to this participant.")
    if row.data_source != owner.data_source:
        fail(409, "reference_source_mismatch", "Context records must have matching provenance.")
    return row


def assess(db, kind, row, owner, clock):
    bad = lambda why: unavailable(kind, why, record_id=row.id)
    if row.participant_id != owner.id or row.data_source != owner.data_source:
        return bad("identity_or_source_mismatch")
    # The current release deliberately enables new mappings only for synthetic data.
    if owner.data_source != "synthetic_demo":
        return bad("synthetic_mapping_only")
    try:
        result = row.result
        created = instant(row.created_at)
        when = instant(row.as_of if kind == "risk" else row.recorded_at or row.created_at)
        if created > clock or when > clock:
            return bad("future_result")
        if (clock - when).total_seconds() > MAX_AGE_SECONDS[kind]:
            return bad("stale_result")
        if kind == "facial":
            if row.kind != "checkin":
                return bad("checkin_required")
            q = result.get("quality") or {}
            if row.status != "accepted" or q.get("status") != "accepted":
                return bad("insufficient_quality")
            if not number(q.get("elapsed_duration_sec")) or when + timedelta(seconds=q["elapsed_duration_sec"]) > clock:
                return bad("unfinished_or_invalid_capture")
            if not number(q.get("usable_fraction")) or q["usable_fraction"] < .8 or not number(q.get("usable_duration_sec")) or q["usable_duration_sec"] < 8:
                return bad("insufficient_quality")
            baseline = db.get(FacialBaseline, row.baseline_id) if row.baseline_id else None
            if baseline is None or baseline.participant_id != owner.id or baseline.data_source != owner.data_source:
                return bad("baseline_unavailable")
            if instant(baseline.effective_at) > when or baseline.summary.get("extractor_version") != result.get("extractor_version"):
                return bad("incompatible_baseline")
            if (result.get("evidence") or {}).get("model_version") != "c1-statistical-v1.0.0":
                return bad("unsupported_model_version")
            dev = (result.get("deviation") or {}).get("mean_absolute_standardized_deviation")
            if not number(dev):
                return bad("deviation_unavailable")
            temporal = result.get("temporal") or {}
            fraction = temporal.get("return_fraction")
            if temporal.get("status") == "measured" and not number(fraction):
                return bad("invalid_temporal_result")
            persistent = dev >= 2 and temporal.get("status") == "measured" and number(fraction) and fraction <= .25
            if dev >= 2 and temporal.get("status") != "measured":
                return bad("temporal_result_unavailable")
            label = "persistent_visual_change" if persistent else "returned_or_stable_visual"
        elif kind == "voice":
            q, prediction = result.get("quality") or {}, result.get("prediction") or {}
            if row.status != "accepted" or q.get("status") != "accepted":
                return bad("insufficient_quality")
            if row.recorded_at and (not number(q.get("duration_sec")) or when + timedelta(seconds=q["duration_sec"]) > clock):
                return bad("unfinished_or_invalid_capture")
            if result.get("feature_schema_version") != "egemaps-v02-functionals-88-16k-v1":
                return bad("unsupported_feature_schema")
            style = prediction.get("predicted_emotion_style")
            if style not in {"neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"} or not row.model_id:
                return bad("prediction_unavailable")
            label = "sad_style_fixture" if style == "sad" else "other_style_fixture"
        else:
            risk = result.get("risk") or {}
            if row.status != "demo_only_prediction" or (result.get("snapshot") or {}).get("status") != "sufficient_history":
                return bad("prediction_unavailable")
            if (result.get("evidence") or {}).get("training_data_source") != owner.data_source:
                return bad("model_source_mismatch")
            p = risk.get("model_probability")
            if not number(p) or not 0 <= p <= 1 or not row.model_id:
                return bad("prediction_unavailable")
            label = "higher_exhaustion_proxy" if p >= .5 else "lower_exhaustion_proxy"
        return mapped(kind, row.id, when.isoformat(), label)
    except (TypeError, ValueError, KeyError, AttributeError):
        return bad("incompatible_result")


def resolve(db, owner, clock, mode="latest_eligible", refs=None, demo_context_id=None):
    refs = refs or {}
    # Validate explicit references even when this strategy is configured to ignore them.
    explicit = {k: owned_reference(db, table, refs[field], owner)
                for k, (table, field) in TABLES.items() if refs.get(field)}
    fixture = owned_reference(db, InterventionDemoContext, demo_context_id, owner) if demo_context_id else None
    modalities = {k: unavailable(k) for k in BASE_WEIGHTS}
    if mode == "none":
        return normalize({k: unavailable(k, "context_disabled") for k in BASE_WEIGHTS}, clock, mode)
    if fixture:
        for k in BASE_WEIGHTS:
            item = fixture.result["modalities"][k]
            if owner.data_source != "synthetic_demo":
                modalities[k] = unavailable(k, "synthetic_mapping_only")
            elif instant(fixture.created_at) > clock or clock > instant(fixture.expires_at):
                modalities[k] = unavailable(k, "expired_demo_context", origin="synthetic_fixture")
            elif item["available"]:
                modalities[k] = mapped(k, fixture.id, fixture.created_at, item["mapping_key"], "synthetic_fixture")
            else:
                modalities[k] = unavailable(k, item["reason"], origin="synthetic_fixture")
        return normalize(modalities, clock, mode, fixture.id)
    for k, (table, _) in TABLES.items():
        if k in explicit:
            modalities[k] = assess(db, k, explicit[k], owner, clock)
            continue
        if mode == "explicit_refs":
            continue
        query = select(table).where(table.participant_id == owner.id, table.data_source == owner.data_source)
        if k == "facial":
            query = query.where(table.kind == "checkin")
        # Bound the scan and prefer the latest assessment time, not a later backfill.
        observation = table.as_of if k == "risk" else table.recorded_at
        rows = db.scalars(query.order_by(observation.desc(), table.created_at.desc(), table.id).limit(50)).all()
        for row in rows:
            candidate = assess(db, k, row, owner, clock)
            if modalities[k]["record_id"] is None:
                modalities[k] = candidate
            if candidate["available"]:
                modalities[k] = candidate
                break
    return normalize(modalities, clock, mode)
