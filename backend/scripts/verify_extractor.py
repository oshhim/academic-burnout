"""Optional native smoke test on a generated no-face clip, not human data."""
import argparse
import tempfile
from pathlib import Path

import numpy as np

from scripts.extract_video import extract


def main():
    import cv2
    parser = argparse.ArgumentParser(description="Verify native MediaPipe/model/video integration on a blank clip; no camera or person is used.")
    parser.add_argument("--model", required=True, type=Path)
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error("Model task file does not exist")
    with tempfile.TemporaryDirectory(prefix="empath-extractor-") as folder:
        path = Path(folder) / "blank.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240))
        if not writer.isOpened():
            raise RuntimeError("OpenCV video writer could not open")
        try:
            for _ in range(150):
                writer.write(np.full((240, 320, 3), 127, dtype=np.uint8))
        finally:
            writer.release()
        windows = extract(path, args.model, protocol="neutral_only")
        assert len(windows) == 6
        assert all(w.quality.face_count == 0 and w.quality.tracking_score == 0 for w in windows)
        assert sum(w.duration_sec for w in windows) == 15
    print("PASS: native model loaded; generated 15-second video decoded; six no-face windows emitted. Facial accuracy remains unvalidated.")


if __name__ == "__main__":
    main()
