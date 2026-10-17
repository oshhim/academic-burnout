"""Feature adapter for MediaPipe Tasks results. No model import at API startup."""
import numpy as np

from app.schemas import Features, Quality, Window

LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)


def eye_ratio(landmarks, indices, width, height):
    points = np.array([(landmarks[i].x * width, landmarks[i].y * height) for i in indices])
    horizontal = np.linalg.norm(points[0] - points[3])
    if horizontal < 1e-6:
        raise ValueError("Degenerate eye landmarks")
    return float((np.linalg.norm(points[1] - points[5]) + np.linalg.norm(points[2] - points[4])) / (2 * horizontal))


def head_angles(matrix):
    rotation = np.asarray(matrix, dtype=float)[:3, :3]
    # Remove any uniform/per-axis scale from the transformation columns.
    rotation = rotation / np.maximum(np.linalg.norm(rotation, axis=0), 1e-9)
    pitch = np.degrees(np.arctan2(rotation[2, 1], rotation[2, 2]))
    yaw = np.degrees(np.arctan2(-rotation[2, 0], np.hypot(rotation[0, 0], rotation[1, 0])))
    roll = np.degrees(np.arctan2(rotation[1, 0], rotation[0, 0]))
    return np.array([pitch, yaw, roll])


def frame_measurement(result, gray, sharpness):
    """Return transient numerical data; landmarks are not retained in JSON."""
    count = len(result.face_landmarks)
    empty = {"face_count": count, "brightness": float(np.mean(gray) / 255), "sharpness": float(np.clip(sharpness / 150, 0, 1)), "features": None, "pose": None}
    if count != 1 or not result.face_blendshapes or not result.facial_transformation_matrixes:
        return empty
    height, width = gray.shape
    try:
        ear = np.mean([eye_ratio(result.face_landmarks[0], eye, width, height) for eye in (LEFT_EYE, RIGHT_EYE)])
        coefficients = {item.category_name: item.score for item in result.face_blendshapes[0]}
        required = ("browDownLeft", "browDownRight", "mouthPressLeft", "mouthPressRight", "jawOpen")
        if any(key not in coefficients for key in required) or not np.isfinite(ear) or not 0.02 <= ear <= 1:
            return empty
        features = {"eye_aspect_ratio": float(ear), "brow_lowering": float(np.mean([coefficients["browDownLeft"], coefficients["browDownRight"]])), "lip_press": float(np.mean([coefficients["mouthPressLeft"], coefficients["mouthPressRight"]])), "jaw_open": float(coefficients["jawOpen"])}
        pose = head_angles(result.facial_transformation_matrixes[0])
        if not np.all(np.isfinite(pose)) or not all(np.isfinite(v) for v in features.values()):
            return empty
        return {**empty, "features": features, "pose": pose.tolist()}
    except (ValueError, IndexError, TypeError):
        return empty


def summarize_window(frames, start, duration, phase):
    valid = [f for f in frames if f["face_count"] == 1 and f["features"] is not None]
    tracking = len(valid) / len(frames) if frames else 0.0
    # Fail an entire window containing multiple faces; don't hide them in a mean.
    count = max((f["face_count"] for f in frames), default=0)
    features = {"eye_aspect_ratio": 0.3, "brow_lowering": 0.0, "lip_press": 0.0, "jaw_open": 0.0, "head_motion_deg": 0.0}
    yaw, pitch = 0.0, 0.0
    if valid:
        for key in tuple(features)[:-1]:
            features[key] = float(np.mean([f["features"][key] for f in valid]))
        poses = np.rad2deg(np.unwrap(np.deg2rad([f["pose"] for f in valid]), axis=0))
        motion = np.sqrt(np.mean(np.sum((poses - np.mean(poses, axis=0)) ** 2, axis=1)))
        features["head_motion_deg"] = float(min(motion, 180))
        # Worst pose within this window rather than canceling opposite directions.
        pitch = float(max((f["pose"][0] for f in valid), key=abs))
        yaw = float(max((f["pose"][1] for f in valid), key=abs))
    return Window(t_start_sec=start, duration_sec=duration, phase=phase,
                  features=Features(**features), quality=Quality(face_count=count, tracking_score=tracking,
                  brightness=float(np.mean([f["brightness"] for f in frames])) if frames else 0.0,
                  sharpness=float(np.mean([f["sharpness"] for f in frames])) if frames else 0.0,
                  yaw_deg=yaw, pitch_deg=pitch))

