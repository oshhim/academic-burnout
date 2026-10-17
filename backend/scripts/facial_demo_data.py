"""Deterministic synthetic numerical features, never participant observations."""
from datetime import datetime, timedelta, timezone

CENTRE = {"eye_aspect_ratio": 0.3, "brow_lowering": 0.1, "lip_press": 0.08, "jaw_open": 0.04, "head_motion_deg": 1.0}
QUALITY = {"face_count": 1, "tracking_score": 0.95, "brightness": 0.55, "sharpness": 0.85, "yaw_deg": 2.0, "pitch_deg": 1.0}


def session(participant_id, name, *, at=None, calibration=False, scenario="return", source="synthetic_demo"):
    at = at or datetime.now(timezone.utc) - timedelta(hours=1)
    shifts = {"stable": (0.0, 0.005, 0.0), "return": (0.0, 0.09, 0.015), "persistent": (0.0, 0.09, 0.105), "poor_quality": (0.0, 0.09, 0.015)}[scenario]
    windows = []
    for i in range(6 if calibration else 18):
        phase_index = 0 if calibration else i // 6
        shift = (int(name[-1]) - 1) * 0.003 if calibration else shifts[phase_index]
        # Minor deterministic jitter makes windows different without random tests.
        shift += (-1 if i % 2 else 1) * 0.001
        features = {k: v + (-shift if k == "eye_aspect_ratio" else shift * 10 if k == "head_motion_deg" else shift) for k, v in CENTRE.items()}
        quality = dict(QUALITY)
        if scenario == "poor_quality":
            quality.update(face_count=0, tracking_score=0.1, brightness=0.05)
        windows.append({"t_start_sec": i * 2.5, "duration_sec": 2.5, "phase": ("neutral", "task", "recovery")[phase_index], "features": features, "quality": quality})
    return {"participant_id": participant_id, "client_session_id": name, "data_source": source, "feature_schema_version": "facial-window-v1", "extractor_version": "synthetic-v1", "recorded_at": at.isoformat(), "consent": True, "baseline_condition_confirmed": calibration, "protocol": "neutral_only" if calibration else "neutral_task_recovery", "windows": windows}


def calibration_sessions(participant_id):
    start = datetime.now(timezone.utc) - timedelta(days=3)
    return [session(participant_id, f"calibration-{i}", calibration=True, at=start + timedelta(hours=i)) for i in range(3)]

