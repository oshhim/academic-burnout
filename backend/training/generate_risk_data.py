"""Synthetic longitudinal simulator. No genuine participant observations."""
import argparse
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from app.risk.schemas import STUDY_TIMEZONE

GENERATOR_VERSION = "latent-ar-exhaustion-simulator-v1"


def generate(participants=240, days=98, seed=73, shifted=False):
    rng = np.random.default_rng(seed)
    start = date(2025, 1, 1)
    people = []
    for i in range(participants):
        pid = f"{"SHIFT" if shifted else "SIM"}-{i:04d}"
        baseline = rng.normal(0, 0.55)
        latent, pressure = baseline, rng.normal(0, 0.3)
        exam_center = rng.integers(28, days - 12)
        phase = rng.uniform(0, 2 * np.pi)
        dropout = rng.uniform(.02, .15) + (.12 if shifted else 0)
        daily, weekly = [], []
        for d in range(days):
            observed = start + timedelta(days=d)
            at = datetime.combine(observed, time(21), ZoneInfo(STUDY_TIMEZONE)).astimezone(timezone.utc)
            pressure = 0.88 * pressure + rng.normal(0, .27 if not shifted else .43)
            exam = 1.2 * np.exp(-((d - exam_center) / 12) ** 2)
            periodic = .22 * np.sin(d * 2 * np.pi / 21 + phase)
            shock = rng.normal(0, 1.1) if rng.random() < .025 else 0
            latent = .91 * latent + .09 * (baseline + pressure + exam + periodic + (.35 if shifted else 0)) + rng.normal(0, .12) + shock * .2
            def rating(value, noise=.42):
                return int(np.clip(np.rint(value + rng.normal(0, noise)), 1, 5))
            reported_at = at + timedelta(hours=int(rng.choice([0, 0, 0, 1, 24, 48])))
            ingested_at = reported_at + timedelta(minutes=int(rng.integers(1, 31)))
            study = int(np.clip(165 + 75 * exam + 38 * pressure + rng.normal(0, 55), 0, 600))
            planned = int(rng.integers(2, 9))
            completed = int(rng.binomial(planned, np.clip(.87 - .12 * max(latent, 0), .25, .98)))
            sleep = round(float(np.clip(7.55 - .7 * latent - .2 * pressure + rng.normal(0, .55), 3.5, 10)), 2)
            row = {"record_id": f"{pid}-d{d}", "client_record_id": f"day-{d}", "participant_id": pid, "data_source": "synthetic_demo", "consent": True,
                   "observed_on": observed.isoformat(), "reported_at": reported_at.isoformat(), "ingested_at": ingested_at.isoformat(),
                   "sleep_hours": sleep, "study_minutes": study, "break_minutes": int(np.clip(60 - 10 * latent + rng.normal(0, 18), 0, 180)),
                   "late_study_minutes": int(study * np.clip(.08 + .07 * max(latent, 0) + rng.normal(0, .04), 0, .65)),
                   "planned_tasks": planned, "completed_tasks": completed,
                   "fatigue": rating(2.35 + .95 * latent), "mental_strain": rating(2.3 + .8 * latent + .2 * pressure), "concentration_readiness": rating(3.8 - .8 * latent)}
            if rng.random() < .08:
                row["sleep_hours"] = None
            if rng.random() < .1:
                row["fatigue"] = row["mental_strain"] = row["concentration_readiness"] = None
            if rng.random() >= dropout:
                daily.append(row)
            if d % 7 == 6 and rng.random() > (.05 if not shifted else .15):
                # A noisy future latent state creates the outcome; no feature
                # threshold is copied to manufacture a deterministic target.
                weekly.append({"record_id": f"{pid}-w{d}", "client_record_id": f"week-{d}", "participant_id": pid, "data_source": "synthetic_demo", "consent": True,
                               "observed_on": observed.isoformat(), "reported_at": reported_at.isoformat(), "ingested_at": ingested_at.isoformat(),
                               "instrument_version": "exploratory-exhaustion-item-v1", "exhaustion": rating(2.35 + 1.05 * latent, .6),
                               "disengagement": rating(2.15 + .8 * latent), "academic_efficacy": rating(3.9 - .8 * latent)})
        people.append({"participant_id": pid, "data_source": "synthetic_demo", "daily": daily, "weekly": weekly})
    return {"dataset_name": "SYNTHETIC longitudinal technical fixtures", "data_source": "synthetic_demo", "generator_version": GENERATOR_VERSION,
            "seed": seed, "study_timezone": STUDY_TIMEZONE, "start_date": start.isoformat(), "days": days,
            "shifted": shifted, "warning": "Simulated observations/outcomes; not measured student data or clinical validation.", "participants": people}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--participants", type=int, default=240)
    parser.add_argument("--days", type=int, default=98)
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--shifted", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/synthetic/risk_dataset.json"))
    args = parser.parse_args()
    if not 30 <= args.participants <= 2000 or not 84 <= args.days <= 365:
        parser.error("Use 30–2000 synthetic participants and 84–365 days for this training evaluation design.")
    data = generate(args.participants, args.days, args.seed, args.shifted)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"Generated SYNTHETIC data: {len(data["participants"])} simulated participants; {args.days} days each. Saved {args.output}")
