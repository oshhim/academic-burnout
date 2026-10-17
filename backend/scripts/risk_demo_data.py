from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.risk.schemas import STUDY_TIMEZONE


def demo_observations(pid, profile="steady", source="synthetic_demo"):
    today = datetime.now(timezone.utc).astimezone(ZoneInfo(STUDY_TIMEZONE)).date()
    records = []
    count = 3 if profile == "sparse" else 14
    for i in range(count):
        day = today - timedelta(days=count - i)
        rising = profile == "rising"
        sleep = round(7.9 - .23 * i, 2) if rising else 7.8
        study = 180 + i * 16 if rising else 160
        fatigue = min(5, 2 + i // 3) if rising else 2
        records.append({"participant_id": pid, "client_record_id": f"daily-{i}", "data_source": source, "consent": True,
            "observed_on": day.isoformat(), "reported_at": datetime.combine(day, time(21), ZoneInfo(STUDY_TIMEZONE)).astimezone(timezone.utc).isoformat(),
            "sleep_hours": sleep, "study_minutes": study, "break_minutes": max(10, 65 - i * 4) if rising else 65,
            "late_study_minutes": min(study, 25 + i * 11) if rising else 10,
            "planned_tasks": 6, "completed_tasks": max(1, 5 - i // 3) if rising else 6,
            "fatigue": fatigue, "mental_strain": fatigue, "concentration_readiness": 6 - fatigue})
    weekly = []
    if profile not in {"missing_weekly", "sparse"}:
        for i, days_ago in enumerate((8, 1)):
            day = today - timedelta(days=days_ago)
            weekly.append({"participant_id": pid, "client_record_id": f"weekly-{i}", "data_source": source, "consent": True,
                "observed_on": day.isoformat(), "reported_at": datetime.combine(day, time(21), ZoneInfo(STUDY_TIMEZONE)).astimezone(timezone.utc).isoformat(),
                "instrument_version": "exploratory-exhaustion-item-v1", "exhaustion": (3 if i == 0 else 5) if profile == "rising" else 2,
                "disengagement": 4 if profile == "rising" else 2, "academic_efficacy": 2 if profile == "rising" else 4})
    return records, weekly
