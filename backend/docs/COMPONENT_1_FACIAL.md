# Component 1 — Facial behaviour: algorithm and API contracts

## Intended research contribution

This prototype implements participant-specific reference comparison, with capture-quality gating, feature-level explanations, temporal response measurements and self-report collection. The proposed research question is whether a reliable personal reference adds useful information compared with a population/static-feature baseline in your student setting. Originality and usefulness still require a literature review and a real study; working code alone does not prove novelty.

The input is **numerical facial behaviour**, not face recognition or identity matching. The output is **change relative to this person's selected reference**, not the person's internal emotion or a burnout diagnosis.

## Input protocol

- Reference: `neutral_only`, typically 15 seconds, confirm reference conditions and explicit consent; minimum three accepted **distinct recording sessions**. Use multiple days for research. Unique IDs prevent retries being counted twice; the server cannot prove a caller captured three different videos.
- Check-in: typically 45 seconds with 15 seconds neutral, 15 seconds of a supervisor-approved ordinary task and 15 seconds of quiet observation. These are capture phase labels; the word `recovery` does not prove psychological recovery. The task and its exact timing must be standardized in the study.
- A neutral-only check-in is also supported; it yields a deviation without temporal measurements.
- Windows: 0.1–5 seconds each, typically 2.5; chronological, non-overlapping, ordered neutral/task/recovery, total elapsed time 10–180 seconds. Empty or incomplete phases are not synthesized.
- `recorded_at` is actual recording start, timezone-aware. No session more than five minutes in the future is accepted. Start-time offsets and gaps reduce coverage.
- `extractor_version` identifies exact feature definitions, preprocessing, model and package version. A reference/check-in mismatch is rejected. Change it whenever feature semantics or preprocessing changes.
- `data_source` is `synthetic_demo` or `local_research`; a participant cannot mix them. Real collection defaults off.

## Feature definitions

| Field | Unit / meaning | Optional adapter |
|---|---|---|
| eye_aspect_ratio | Dimensionless window mean, 0.02–1 | Mean of left/right six-landmark eye aspect ratios in pixel coordinates |
| brow_lowering | 0–1 coefficient window mean | Mean `browDownLeft`, `browDownRight` coefficients |
| lip_press | 0–1 coefficient window mean | Mean `mouthPressLeft`, `mouthPressRight` coefficients |
| jaw_open | 0–1 coefficient window mean | `jawOpen` coefficient |
| head_motion_deg | Degrees, 0–180 | RMS Euclidean variation of pitch/yaw/roll about the window mean, with angular unwrapping |

Coefficients are geometric expression parameters, **not emotion probabilities**. For a camera frontend, match these exact definitions or create a new extractor version and recalibrate. Landmark meshes are used transiently in the optional adapter; only these aggregates are written to JSON.

## Quality gate

Each window requires exactly one face, tracking score ≥0.6, brightness within [0.15,0.95], sharpness ≥0.35, absolute yaw ≤35° and pitch ≤30°. Defaults are provisional engineering choices that must be tuned and evaluated locally.

For the optional adapter: `tracking_score` means the proportion of sampled frames with exactly one face **and usable features**, not a neural-network confidence. Brightness is full-frame grayscale mean/255. Sharpness is clipped grayscale Laplacian variance/150; it depends on capture resolution. Pose is the largest absolute frame pose per window. These are heuristics, not validated imaging-quality instruments.

Accepted session: ≥8 usable seconds and ≥80% usable temporal coverage. Coverage = accepted-window duration / elapsed end time. Quality score = coverage × duration-weighted tracking score. This describes capture quality, not accuracy/confidence of a wellbeing prediction.

Rejected session: persist status/reasons and numerical input for debugging/export; return no aggregate deviation or temporal conclusion; request self-report. There is no raw media stored. Define a retention policy before collecting real records: this package retains numerical data until participant deletion.

## Robust reference model

Let `x_sj` be the duration-weighted mean of accepted windows for feature `j` in calibration session `s`.

```text
center_j = median_s(x_sj)
MAD_j = median_s(abs(x_sj - center_j))
scale_j = max(1.4826 * MAD_j, floor_j)
```

Floors: EAR/brow/lip/jaw = 0.025; head motion = 1 degree. This stabilizes tiny/zero reference variance. Median/MAD describes a robust scale; it does not imply normality or establish a clinical reference interval. Three sessions are a software minimum, not a sufficiently powered personalized model.

Baselines are immutable. Each stores source calibration IDs, extractor version, center, scale, model/schema version and an incrementing version. Repeating the same calibration selection returns the same baseline. The baseline is chronologically effective at the latest calibration **end**. A check-in cannot use future calibration observations; old check-ins keep the baseline they used when computed. Creating new references does not overwrite or retrospectively recompute old outputs.

## Deviation calculation

```text
z_j = (checkin_mean_j - center_j) / scale_j
score = mean_j(abs(z_j))
```

The result includes signed per-feature standardized deviations and the three largest absolute contributors. Increasing EAR and decreasing EAR can both produce a change score; the signed features preserve direction. Equal weights are used; correlations between features are not accounted for. A median/MAD standardized value is not a p-value.

Provisional display categories: score <1 `within_reference_range`; 1≤score<2 `moderate_visual_change`; score≥2 `large_visual_change`. These are **engineering labels**, not validated healthy/stressed boundaries. The API returns no stress percentage or clinical confidence.

## Temporal measurement

Calculate deviation independently for each phase using accepted windows. All three phases require ≥5 usable seconds. Task must exceed neutral by >0.25 standardized score and be ≥0.5; otherwise the fraction is not measurable.

```text
change = task_score - recovery_score
return_fraction = change / task_score
return_rate_z_per_sec = change / (recovery_midpoint - task_midpoint)
```

Midpoints are actual duration-weighted time centres of accepted windows. Positive values mean closer to reference; negative values mean farther away. Fraction 0.5 means the recovery-phase visual score is half the task-phase score; it does not mean a 50% wellbeing improvement. The metric compares phase means, not a fitted recovery curve, return time, causality or physiological rate.

## Endpoints

All below begin with `/api/v1` and require `X-API-Key`. Interactive request schemas and examples are generated at `/docs`; machine-readable schema is `/openapi.json`.

| Method | Path | Purpose |
|---|---|---|
| POST | /participants | Register participant provenance and consent version |
| GET | /participants/{id}/export | Export that participant's numerical inputs, results, baselines and self-reports |
| DELETE | /participants/{id} | Delete that participant and associated records |
| GET | /models | Honest implementation/model status across all four components |
| GET | /facial/config | Feature schema and current thresholds |
| POST | /facial/calibrations | Validate and persist one reference recording |
| POST | /facial/baselines | Create immutable reference from 3–10 accepted calibration IDs |
| GET | /facial/baselines/{id} | Retrieve reference versions for a participant |
| POST | /facial/checkins | Evaluate with an explicit or latest eligible baseline |
| GET | /facial/history/{id} | Paginated check-ins; `kind=all` includes calibration |
| POST | /facial/self-reports/{session_id} | Attach immutable 1–5 ratings |
| GET | /facial/self-reports/{session_id} | Retrieve that self-report |

`client_session_id` is unique per participant across calibration and check-in. Retrying identical session content returns the stored result/session ID. Reusing the client ID with changed content gives HTTP 409. Baseline selection is deduplicated independently. Successful create/replay calls return 201. Self-report retries are idempotent; a changed response is rejected rather than silently changing research labels.

Self-report fields are exploratory fatigue, mental strain and concentration readiness on an integer 1–5 scale. They are not a validated burnout instrument. Request labels for every session to avoid collecting only selected uncertain cases. Research validity should use approved instruments and a predefined analysis plan. Labels are captured but do not alter the visual deviation calculation.

Responses include data source, extractor/model/schema version, baseline used, quality/reasons, deviation and temporal availability, warning messages, request ID and processing-time header. HTTP 401 = key; 403 = consent/research gate; 404 = missing/wrong-owner record; 409 = state, chronology or ID conflict; 422 = input contract; 413 = >configured request size.

## Research validation after the prototype

Collect approved repeated recordings, capture context (device, lighting, time, glasses where relevant), task protocol and concurrent self-report. Evaluate reference stability, rejected-capture rate, repeatability, within-person relationships and the extra value of the personalized/temporal features. Use participant-separated splits for supervised extensions; use chronologically prior calibration only. Compare a population/static reference, personal reference and personal + temporal features. Track missing modalities and report error/rejection distributions across conditions.

No performance estimate on synthetic inputs can answer those questions. A successful progress demo establishes software readiness; it does not establish wellbeing validity or worldwide originality.

## Primary implementation references

- FastAPI SQL databases: <https://fastapi.tiangolo.com/tutorial/sql-databases/>
- Pydantic validators: <https://docs.pydantic.dev/latest/concepts/validators/>
- SQLAlchemy sessions: <https://docs.sqlalchemy.org/en/20/orm/session_basics.html>
- MediaPipe Face Landmarker Python: <https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python>

These document the software/feature-extraction APIs, not validation of the project's wellbeing hypothesis.
