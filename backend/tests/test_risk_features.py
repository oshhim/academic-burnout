from datetime import datetime, timedelta, timezone

import pytest

from app.risk.features import parse_time, snapshot
from scripts.risk_demo_data import demo_observations


def records(profile="steady"):
    daily, weekly = demo_observations("R1", profile)
    cutoff = datetime.now(timezone.utc)
    for i, row in enumerate(daily + weekly):
        row["record_id"] = f"record-{i}"
        row["ingested_at"] = row["reported_at"]
    return daily, weekly, cutoff


def test_point_in_time_ignores_future_outcome_and_backfill():
    daily, weekly, at = records()
    baseline = snapshot(daily, weekly, at)
    future = {**weekly[-1], "record_id": "future-label", "observed_on": (at.date() + timedelta(days=5)).isoformat(), "reported_at": (at + timedelta(days=5)).isoformat(), "ingested_at": (at + timedelta(days=5)).isoformat(), "exhaustion": 5}
    assert snapshot(daily, [*weekly, future], at)["features"] == baseline["features"]
    daily[-1]["ingested_at"] = (at + timedelta(seconds=1)).isoformat()
    later = snapshot(daily, weekly, at)
    assert later["daily_report_count"] == 13
    assert daily[-1]["record_id"] not in later["input_record_ids"]["daily"]


def test_observation_and_availability_are_both_required():
    daily, weekly, at = records()
    daily[-1]["reported_at"] = (at + timedelta(seconds=1)).isoformat()
    daily[-1]["ingested_at"] = (at - timedelta(seconds=1)).isoformat()
    assert snapshot(daily, weekly, at)["daily_report_count"] == 13


def test_time_zone_boundary_uses_colombo_complete_day():
    at = datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc)  # 00:30 on Oct 11 locally.
    snap = snapshot([], [], at)
    assert snap["lookback_end"] == "2026-10-10"
    assert snap["lookback_start"] == "2026-09-27"
    assert snap["target_start"] == "2026-10-12"


def test_missing_is_not_zero_and_ratios_respect_zero_denominators():
    daily, weekly, at = records("missing_weekly")
    for r in daily:
        r["sleep_hours"] = None
        r["study_minutes"] = r["late_study_minutes"] = 0
        r["planned_tasks"] = r["completed_tasks"] = 0
    snap = snapshot(daily, weekly, at)
    assert snap["features"]["sleep_hours_mean"] is None
    assert snap["features"]["study_minutes_mean"] == 0
    assert snap["features"]["completion_ratio"] is None
    assert snap["features"]["late_study_fraction"] is None
    assert snap["features"]["weekly_missing"] == 1


def test_slope_uses_calendar_spacing_not_row_number():
    daily, weekly, at = records()
    selected = [daily[0], daily[3], daily[9]]
    for row, value in zip(selected, [5.0, 8.0, 14.0]):
        row["sleep_hours"] = value
    assert snapshot(selected, weekly, at)["features"]["sleep_hours_slope"] == pytest.approx(1.0)


def test_minimum_history_and_duplicates():
    daily, weekly, at = records("sparse")
    snap = snapshot(daily, weekly, at)
    assert snap["status"] == "insufficient_history"
    with pytest.raises(ValueError):
        snapshot([*daily, daily[0]], weekly, at)


def test_knowledge_cutoff_includes_equal_timestamp():
    daily, weekly, at = records()
    daily[-1]["ingested_at"] = at.isoformat()
    assert snapshot(daily, weekly, at)["daily_report_count"] == 14

