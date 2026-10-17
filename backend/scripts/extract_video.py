"""Optional offline local-video adapter. Writes numerical JSON, never sends it."""
import argparse
import hashlib
import json
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from app.facial.extraction import frame_measurement, summarize_window
from app.schemas import SessionInput


def extract(video_path, model_path, *, protocol):
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not cap.isOpened() or fps <= 0 or fps > 240:
        cap.release()
        raise ValueError("Cannot read video or its FPS is invalid; use a constant-frame-rate MP4.")
    options = vision.FaceLandmarkerOptions(base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO, num_faces=2, output_face_blendshapes=True,
        output_facial_transformation_matrixes=True, min_face_detection_confidence=0.6,
        min_face_presence_confidence=0.6, min_tracking_confidence=0.6)
    limit = 15 if protocol == "neutral_only" else 45
    frames_by_window, index, last_timestamp = {}, 0, -1
    try:
        with vision.FaceLandmarker.create_from_options(options) as landmarker:
            while index / fps < limit:
                ok, frame = cap.read()
                if not ok:
                    break
                time_sec = index / fps
                # Sample at approximately 10Hz; timestamps always strictly increase.
                if index % max(1, round(fps / 10)) == 0:
                    timestamp = max(last_timestamp + 1, round(time_sec * 1000))
                    last_timestamp = timestamp
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                    measurement = frame_measurement(result, gray, sharpness)
                    frames_by_window.setdefault(int(time_sec / 2.5), []).append(measurement)
                index += 1
    finally:
        cap.release()
    actual_duration = min(index / fps, limit)
    windows = []
    for i, frames in sorted(frames_by_window.items()):
        start = i * 2.5
        duration = min(2.5, actual_duration - start)
        if duration < 0.1:
            continue
        phase = "neutral" if protocol == "neutral_only" else ("neutral", "task", "recovery")[min(int(start / 15), 2)]
        windows.append(summarize_window(frames, start, duration, phase))
    return windows


def main():
    parser = argparse.ArgumentParser(description="Read an explicitly supplied local video. Requires optional dependencies and a MediaPipe task file.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--participant-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--recorded-at", required=True, help="Actual recording start with timezone; never silently guessed.")
    parser.add_argument("--protocol", choices=["neutral_only", "neutral_task_recovery"], required=True)
    parser.add_argument("--consent", action="store_true", help="Assert that the person explicitly consented to local processing.")
    parser.add_argument("--baseline-condition-confirmed", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.consent:
        parser.error("--consent is required before processing a person's recording.")
    if args.protocol == "neutral_only" and not args.baseline_condition_confirmed:
        parser.error("Reference calibration needs --baseline-condition-confirmed.")
    for file in (args.video, args.model):
        if not file.is_file():
            parser.error(f"Missing file: {file}")
    model_hash = hashlib.sha256(args.model.read_bytes()).hexdigest()[:16]
    payload = SessionInput(participant_id=args.participant_id, client_session_id=args.session_id,
        data_source="local_research", extractor_version=f"mp-{version("mediapipe")}-task-{model_hash}-adapter-v1",
        recorded_at=datetime.fromisoformat(args.recorded_at.replace("Z", "+00:00")), consent=True,
        baseline_condition_confirmed=args.baseline_condition_confirmed, protocol=args.protocol,
        windows=extract(args.video, args.model, protocol=args.protocol))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(f"Saved numerical features to {args.output}. Raw recording remains at its original path; nothing was uploaded.")


if __name__ == "__main__":
    main()

