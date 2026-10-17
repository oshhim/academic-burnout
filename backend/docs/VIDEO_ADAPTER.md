# Optional local-video adapter

The main demo does not need this adapter. This CLI processes an explicitly supplied local video and writes numerical API input JSON. It does not open a webcam, send a video, upload JSON, establish identities or delete your original recording.

The MediaPipe-trained model is used for landmarks/blendshape feature extraction. Personal reference statistics are then computed by our API; there is no trained wellbeing classifier.

## Setup in a separate environment

Use Python 3.11/3.12, compatible with the MediaPipe wheel available for your OS. Keep optional native packages separate from the verified main API environment.

On Ubuntu/Debian Linux the native MediaPipe library also requires EGL/GLES runtime libraries. If they are missing, install them with your normal OS package manager before using the optional adapter:

```bash
sudo apt update
sudo apt install libgles2 libegl1
```

The main API and synthetic demo do not need these libraries. OpenCV is supplied by `opencv-contrib-python`; avoid installing another OpenCV wheel into the same extractor environment.

Windows Command Prompt:

```bat
py -3.12 -m venv .venv-extractor
.venv-extractor\Scripts\activate.bat
python -m pip install -r requirements-extractor.txt
```

macOS/Linux:

```bash
python3.12 -m venv .venv-extractor
source .venv-extractor/bin/activate
python -m pip install -r requirements-extractor.txt
```

From the official [Face Landmarker model page](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker#models), download the Face Landmarker `.task` asset into `models/face_landmarker.task`. This is an optional model download, not included in the repository. Review the model's terms. Download it only through the official page. Exact model SHA-256 prefix, MediaPipe package version and adapter version are placed in `extractor_version`, so references cannot be reused after a model change.

To test native integration without a camera or participant recording:

```bash
python -m scripts.verify_extractor --model models/face_landmarker.task
```

This generates a blank clip in a temporary folder and verifies that no face is inferred. It checks installation/model loading/video decoding, not facial measurement accuracy.

## Record a known protocol

Use a constant-frame-rate MP4, frontal face, stationary camera, usable lighting and enough resolution to see the eyes. The adapter samples around 10Hz. For reference: 15 seconds of confirmed reference conditions. For a check-in: 15 seconds neutral, 15 seconds standardized task and 15 seconds quiet observation. Keep actual recording start and protocol timing. The adapter assigns phases using these fixed boundaries; it does not discover them from facial activity.

Process your own explicitly consented technical recordings only within your supervisor-approved process. Participant research collection requires the appropriate approval/consent. The main backend keeps `ENABLE_RESEARCH_MODE=false` by default; changing a setting is not ethical approval.

## Extract a reference payload

Run from the `backend/` folder in the extractor environment; replace the date/time with the **actual** recording start. Example shown on one line for Windows/Linux compatibility:

```bash
python -m scripts.extract_video --video recordings/reference_01.mp4 --model models/face_landmarker.task --participant-id LOCAL-01 --session-id reference-01 --recorded-at 2026-10-11T09:00:00+00:00 --protocol neutral_only --consent --baseline-condition-confirmed --output data/reference_01.json
```

Repeat for three distinct recordings with different session IDs. All use `data_source=local_research`, never `synthetic_demo`. Register `LOCAL-01` with the same source after research mode is appropriately enabled, submit JSON to `/facial/calibrations`, then use returned IDs to create a baseline.

Check-in extraction:

```bash
python -m scripts.extract_video --video recordings/checkin_01.mp4 --model models/face_landmarker.task --participant-id LOCAL-01 --session-id checkin-01 --recorded-at 2026-10-11T10:00:00+00:00 --protocol neutral_task_recovery --consent --output data/checkin_01.json
```

Submit this JSON to `/facial/checkins`; baseline ID can be omitted to select the latest eligible reference. No automatic transfer is performed. If the video is too short, phases are unavailable; if unusable frames dominate, quality is rejected. Frame-rate and image-quality heuristics must be checked on the target phones.

## Limitations and verification boundary

- Pixel landmarks are transient; full meshes/raw frames are not written to JSON. Original media remains on disk where you supplied it. This tool does not implement automatic erasure.
- Pose angles are approximations from the facial transformation matrix. Test camera/mirroring conventions on your devices. Absolute pose gating reduces sensitivity to sign conventions.
- `num_faces=2` allows detecting a second face; MediaPipe smoothing is not used in this configuration. A window with any multi-face sample is rejected. The software cannot guarantee detection of every bystander.
- RMS angular variation is a motion proxy, not calibrated head motion from medical instrumentation. Face coefficients depend on illumination, occlusions and model limits.
- Adapter numerical helpers are tested. See the release 0.1.0 section of `docs/history/VERIFICATION_HISTORY.md`: the native model/video path was smoke-tested then and has not been re-run since. A no-face smoke test cannot validate facial accuracy.
- For a Flutter/web camera frontend, reproduce this schema/definitions in the client extractor and use a distinct version string; do not mix frontend and Python extractor values without recalibration.
