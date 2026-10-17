"""Point-in-time feature construction shared by training and live inference."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

from app.risk.schemas import STUDY_TIMEZONE

FEATURE_SCHEMA = "daily14-weekly28-exhaustion7-v1"
BEHAVIOR_FEATURES = ["sleep_hours_mean", "sleep_hours_std", "sleep_hours_slope", "study_minutes_mean", "study_minutes_std",
                     "late_study_fraction", "break_minutes_mean", "completion_ratio", "incomplete_task_days_fraction",
                     "daily_coverage_fraction", "behavior_coverage_fraction"]
SELF_REPORT_FEATURES = ["fatigue_mean", "mental_strain_mean", "concentration_readiness_mean", "fatigue_slope",
                        "latest_weekly_exhaustion", "latest_weekly_disengagement", "latest_weekly_academic_efficacy",
                        "weekly_age_days", "weekly_missing"]
FEATURE_NAMES = BEHAVIOR_FEATURES + SELF_REPORT_FEATURES


def parse_time(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def day(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def eligible(record, as_of):
    # Both observation/report time AND server availability time are required.
    return parse_time(record["reported_at"]) <= as_of and parse_time(record["ingested_at"]) <= as_of


def snapshot(daily_records, weekly_records, as_of):
    as_of = parse_time(as_of)
    local_day = as_of.astimezone(ZoneInfo(STUDY_TIMEZONE)).date()
    start, end = local_day - timedelta(days=14), local_day - timedelta(days=1)
    daily = sorted([r for r in daily_records if start <= day(r["observed_on"]) <= end and eligible(r, as_of)], key=lambda r: r["observed_on"])
    weekly = sorted([r for r in weekly_records if local_day - timedelta(days=28) <= day(r["observed_on"]) <= local_day and eligible(r, as_of)], key=lambda r: (r["observed_on"], r["reported_at"]))
    if len({day(r["observed_on"]) for r in daily}) != len(daily):
        raise ValueError("Duplicate daily observations would overweight a day")
    if len({day(r["observed_on"]) for r in weekly}) != len(weekly):
        raise ValueError("Duplicate weekly assessment dates")
    latest = weekly[-1] if weekly else None
    def values(field):
        return [float(r[field]) for r in daily if r.get(field) is not None]
    def average(field):
        v = values(field)
        return float(np.mean(v)) if v else None
    def std(field):
        v = values(field)
        return float(np.std(v)) if len(v) >= 2 else None
    def slope(field):
        rows = [r for r in daily if r.get(field) is not None]
        if len(rows) < 3:
            return None
        x = np.array([(day(r["observed_on"]) - start).days for r in rows], dtype=float)
        if np.ptp(x) < 3:
            return None
        y = np.array([r[field] for r in rows], dtype=float)
        return float(np.dot(x - x.mean(), y - y.mean()) / np.sum((x - x.mean()) ** 2))
    task_rows = [r for r in daily if r.get("planned_tasks") is not None and r["planned_tasks"] > 0]
    late_rows = [r for r in daily if r.get("late_study_minutes") is not None and r.get("study_minutes") is not None]
    study_total = sum(r["study_minutes"] for r in late_rows)
    behavior_days = sum(any(r.get(f) is not None for f in ("sleep_hours", "study_minutes", "planned_tasks")) for r in daily)
    features = {
        "sleep_hours_mean": average("sleep_hours"), "sleep_hours_std": std("sleep_hours"), "sleep_hours_slope": slope("sleep_hours"),
        "study_minutes_mean": average("study_minutes"), "study_minutes_std": std("study_minutes"),
        "late_study_fraction": sum(r["late_study_minutes"] for r in late_rows) / study_total if study_total > 0 else None,
        "break_minutes_mean": average("break_minutes"),
        "completion_ratio": sum(r["completed_tasks"] for r in task_rows) / sum(r["planned_tasks"] for r in task_rows) if task_rows else None,
        "incomplete_task_days_fraction": sum(r["completed_tasks"] < r["planned_tasks"] for r in task_rows) / len(task_rows) if task_rows else None,
        "daily_coverage_fraction": len(daily) / 14, "behavior_coverage_fraction": behavior_days / 14,
        "fatigue_mean": average("fatigue"), "mental_strain_mean": average("mental_strain"),
        "concentration_readiness_mean": average("concentration_readiness"), "fatigue_slope": slope("fatigue"),
        "latest_weekly_exhaustion": float(latest["exhaustion"]) if latest else None,
        "latest_weekly_disengagement": float(latest["disengagement"]) if latest and latest.get("disengagement") is not None else None,
        "latest_weekly_academic_efficacy": float(latest["academic_efficacy"]) if latest and latest.get("academic_efficacy") is not None else None,
        "weekly_age_days": (local_day - day(latest["observed_on"])).days if latest else None,
        "weekly_missing": 0.0 if latest else 1.0,
    }
    reasons = []
    if len(daily) < 7:
        reasons.append("require_at_least_7_distinct_daily_reports_in_prior_14_days")
    if behavior_days < 7:
        reasons.append("require_at_least_7_days_with_sleep_study_or_task_observations")
    if sum(features[k] is not None for k in FEATURE_NAMES) < 10:
        reasons.append("too_many_missing_predictors")
    return {"feature_schema_version": FEATURE_SCHEMA, "study_timezone": STUDY_TIMEZONE, "as_of": as_of.isoformat(timespec="microseconds"),
            "lookback_start": start.isoformat(), "lookback_end": end.isoformat(),
            "target_start": (local_day + timedelta(days=1)).isoformat(), "target_end": (local_day + timedelta(days=7)).isoformat(),
            "status": "sufficient_history" if not reasons else "insufficient_history", "reasons": reasons,
            "daily_report_count": len(daily), "behavior_report_days": behavior_days,
            "weekly_report_available": latest is not None, "features": features,
            "input_record_ids": {"daily": [r["record_id"] for r in daily], "weekly": [latest["record_id"]] if latest else []},
            "missing_feature_names": [f for f in FEATURE_NAMES if features[f] is None]}


def vector(features):
    return [float(features[f]) if features[f] is not None else np.nan for f in FEATURE_NAMES]
