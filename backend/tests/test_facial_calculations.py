import numpy as np
import pytest
from types import SimpleNamespace
from pydantic import ValidationError

from app.facial.calculations import SCALE_FLOORS, aggregate, calculate_baseline, deviation, inspect_quality, temporal_measurements
from app.facial.extraction import LEFT_EYE, RIGHT_EYE, frame_measurement, head_angles, summarize_window
from app.schemas import SessionInput
from scripts.facial_demo_data import CENTRE, session


def parsed(scenario="return"):
    return SessionInput.model_validate(session("P1", "s1", scenario=scenario))


def test_median_mad_resists_one_large_outlier_and_floor_prevents_zero():
    rows = [dict(CENTRE) for _ in range(5)]
    rows[-1] = {key: value + 100 for key, value in CENTRE.items()}
    center, scale = calculate_baseline(rows)
    assert center == CENTRE
    assert scale == SCALE_FLOORS


def test_score_hand_calculated_and_signed():
    changed = {key: value + SCALE_FLOORS[key] * 2 for key, value in CENTRE.items()}
    changed["eye_aspect_ratio"] = CENTRE["eye_aspect_ratio"] - 2 * SCALE_FLOORS["eye_aspect_ratio"]
    score = deviation(changed, CENTRE, SCALE_FLOORS)
    assert score["mean_absolute_standardized_deviation"] == 2
    assert score["per_feature_signed_z"]["eye_aspect_ratio"] == -2
    assert score["level"] == "large_visual_change"


def test_aggregation_uses_duration_weights():
    windows = parsed().windows[:2]
    windows[0].duration_sec = 1
    windows[1].duration_sec = 3
    windows[0].features.eye_aspect_ratio = 0.2
    windows[1].features.eye_aspect_ratio = 0.4
    assert aggregate(windows)["eye_aspect_ratio"] == pytest.approx(0.35)


@pytest.mark.parametrize("scenario,sign", [("return", 1), ("persistent", -1)])
def test_temporal_sign_and_actual_midpoint_rate(scenario, sign):
    payload = parsed(scenario)
    quality, valid = inspect_quality(payload)
    result = temporal_measurements(valid, payload, CENTRE, SCALE_FLOORS)
    assert quality.status == "accepted"
    assert result["status"] == "measured"
    assert sign * result["return_fraction"] > 0
    assert result["return_rate_z_per_sec"] == pytest.approx(result["task_to_recovery_change"] / 15, abs=1e-6)


def test_stable_does_not_invent_a_return_result():
    payload = parsed("stable")
    result = temporal_measurements(payload.windows, payload, CENTRE, SCALE_FLOORS)
    assert result["status"] == "not_measurable"


def test_missing_phase_and_bad_windows_are_not_filled_in():
    payload = parsed()
    for w in payload.windows[-6:]:
        w.quality.face_count = 0
    quality, valid = inspect_quality(payload)
    assert quality.status == "insufficient_quality"
    result = temporal_measurements(valid, payload, CENTRE, SCALE_FLOORS)
    assert result["reason"] == "each_phase_requires_at_least_5_usable_seconds"


def test_gaps_count_against_coverage():
    payload = parsed()
    for w in payload.windows:
        w.t_start_sec += 60
    quality, _ = inspect_quality(payload)
    assert quality.status == "insufficient_quality"
    assert quality.usable_fraction == pytest.approx(45 / 105, abs=1e-6)


@pytest.mark.parametrize("change", ["overlap", "phase_order", "nan", "timezone"])
def test_malformed_schema_is_rejected(change):
    data = session("P1", "s1")
    if change == "overlap":
        data["windows"][1]["t_start_sec"] = 0
    elif change == "phase_order":
        data["windows"][0]["phase"] = "recovery"
    elif change == "nan":
        data["windows"][0]["features"]["lip_press"] = float("nan")
    else:
        data["recorded_at"] = "2026-01-01T12:00:00"
    with pytest.raises(ValidationError):
        SessionInput.model_validate(data)


def test_adapter_pose_and_motion_and_multiface_window():
    assert head_angles(np.eye(4)).tolist() == pytest.approx([0, 0, 0])
    base = {"face_count": 1, "brightness": 0.5, "sharpness": 0.8, "features": {k: v for k, v in CENTRE.items() if k != "head_motion_deg"}, "pose": [0, 0, 0]}
    moved = {**base, "pose": [0, 2, 0]}
    window = summarize_window([base, moved], 0, 2.5, "neutral")
    assert window.features.head_motion_deg == pytest.approx(1)
    assert window.quality.tracking_score == 1
    multi = {**base, "face_count": 2, "features": None}
    window = summarize_window([base, multi], 0, 2.5, "neutral")
    assert window.quality.face_count == 2
    assert window.quality.tracking_score == 0.5


def test_landmark_adapter_eye_geometry_blendshapes_and_no_face():
    landmarks = [SimpleNamespace(x=0.5, y=0.5) for _ in range(478)]
    for indices, offset in ((LEFT_EYE, 0), (RIGHT_EYE, 0.4)):
        for index, (x, y) in zip(indices, ((0.1,0.5), (0.15,0.48), (0.25,0.48), (0.3,0.5), (0.25,0.52), (0.15,0.52))):
            landmarks[index] = SimpleNamespace(x=x + offset, y=y)
    coefficients = [SimpleNamespace(category_name=name, score=score) for name, score in (("browDownLeft", 0.1), ("browDownRight", 0.3), ("mouthPressLeft", 0.2), ("mouthPressRight", 0.4), ("jawOpen", 0.5))]
    result = SimpleNamespace(face_landmarks=[landmarks], face_blendshapes=[coefficients], facial_transformation_matrixes=[np.eye(4)])
    frame = frame_measurement(result, np.full((100, 100), 127), 150)
    assert frame["features"]["eye_aspect_ratio"] == pytest.approx(0.2)
    assert frame["features"]["brow_lowering"] == pytest.approx(0.2)
    assert frame["features"]["lip_press"] == pytest.approx(0.3)
    result.face_landmarks = []
    assert frame_measurement(result, np.full((100, 100), 127), 150)["features"] is None

