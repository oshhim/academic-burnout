# Verification history (releases 0.1.0–0.3.0)

Earlier verification records, kept as they were written. File names here are from before a later renaming; for example `scripts.run_demo` is now `scripts.run_facial_demo`, `examples/demo_results.json` is now `examples/facial_http_results.json`, and `examples/combined_http_results.json` was superseded by `examples/all_components_http_results.json`. The current report is [VERIFICATION.md](../../VERIFICATION.md).

## Release 0.3.0 — C1/C2/C3 (17 October 2026)

- Python 3.12.14, Linux x86_64; pinned dependencies include tzdata for Windows timezone support.
- **68 tests passed** including all earlier C1/C2 tests, C3 ingestion/batch rollback, immutable retries/predictions, input validation, missing-data math, calendar-spaced slopes, Asia/Colombo day boundary, genuine server-availability cutoffs, training/serving feature parity and source gating. A model spy confirms the synthetic estimator is not called for local records. Migration tests preserve C1 and existing C2 voice records while upgrading to 0003.
- Actual HTTP integration verification passed for all three components, including original public WAV uploads and four synthetic C3 profiles. Results are in `examples/all_components_http_results.json`. The temporary database/server are discarded after verification.
- C3 original synthetic run: steady simulation score 0.095135; rising 0.909821; missing-weekly 0.108390; sparse history has null risk. These designed cases have no measured future outcomes and do not establish predictive accuracy.
- Supplied C3 model: 240 simulated people, 98 days, 2,741 eligible windows; 1,276 training examples, 183 held-out-person/later-time test examples. Selected random forest by purged CV; synthetic test AUC 0.8077, Brier 0.1966. Independent shifted-simulator AUC 0.7925. These are simulator checks only. The forest's probability-error score is worse than the dummy prior; no calibration claim is made.
- C1/C2 model artifacts and their original evaluation results remain unchanged. C3 supplies its own model card, synthetic provenance, feature schema, comparison, temporal/person split manifest and clearly labelled PNG/PDF plot.
- No actual local dataset was fitted. The optional local fitting entry point has source/consent/time/sample gates; six-week eligibility does not establish statistical power or clinical validity. Windows/macOS commands and interactive browser clicks were not exercised here; numerical tests and real HTTP requests were.

## Release 0.2.0 — C1/C2

- Python 3.12.14, Linux x86_64. Exact environment is pinned in `requirements-tested.txt`.
- `python -m pytest -q`: **49 passed**. Includes all 26 earlier C1 checks, plus real public-audio inference, quality/decoder cases, model integrity, multipart/JSON upload limits, participant lifecycle and a 0001→0002 migration-preservation check. One upstream Starlette test-client deprecation warning; no failures.
- `python -m scripts.verify_http --output examples/combined_http_results.json`: **passed** with a real Uvicorn process/TCP uploads, migrated temporary SQLite, complete C1 workflow and three actual public WAV voice check-ins. Both demos and the API schema were served successfully.
- `python -m pip check`: no broken dependencies. Python module compilation and both browser JavaScript syntax checks passed. Interactive browser layout/click behaviour was not tested here; the underlying HTTP workflows were.
- Original RAVDESS speech archive (~209 MB) downloaded from Zenodo and verified against publisher MD5. 1,440 original speech WAVs extracted, 1,377 accepted and 63 abstained at the predefined activity gate. No synthetic audio supplied training labels.
- Trained five frozen comparisons using 18 training actors and three actor-group CV folds; six other actors used for test. Selected logistic regression by CV macro F1 0.4753. Accepted test macro F1 0.4905, accuracy 49.42% on 346 recordings. Test coverage 96.11%; counting 14 abstentions as incorrect gives 47.50% across all 360 test files. No local student accuracy is established.
- Native openSMILE 2.6.0 eGeMAPSv02 extraction exercised on original public recordings in training and HTTP inference. The model artifact, model card, full accepted/rejected manifest, evaluation and PNG/PDF plots are included. Downloaded full corpus/feature cache are excluded from the release ZIP.
- Original held-out demo outputs: neutral→neutral; happy→calm; angry→angry. The incorrect happy result is preserved. The three examples are not a separate evaluation and were not used to select the model.
- Windows/macOS instructions are provided but not executed here. Existing C1 native MediaPipe test status below is historical; that optional video environment was not recreated for the C2 release. C1 numerical/API regressions pass.

## Release 0.1.0 — first C1 delivery (11 October 2026)

### Core backend

- Python 3.12.14, Linux x86_64. Exact API/test dependencies: `requirements-tested.txt`.
- `python -m pytest -q`: **26 passed**. One upstream Starlette warning about the future test-client HTTP dependency; no failures.
- `python -m scripts.verify_http --output examples/demo_results.json`: **passed** using a real temporary Uvicorn process, TCP requests and migrated SQLite database. Verified health, demo HTML, Swagger, OpenAPI schema, registration, three calibrations, baseline creation, four check-ins, history and export.
- Core package dependency check: **no broken requirements**.
- Python modules compiled successfully; browser demo JavaScript passed `node --check`.
- The browser page is served and its JavaScript syntax is checked; visual layout/click behaviour was not exercised in an interactive browser during this delivery.

Actual synthetic HTTP results:

| Scenario | Status | Session deviation | Task score | Recovery score | Return fraction |
|---|---|---:|---:|---:|---:|
| stable | accepted | 0.056667 | 0.170000 | 0.000000 | Not measurable |
| return | accepted | 1.190000 | 3.060000 | 0.510000 | 0.833333 |
| persistent | accepted | 2.210000 | 3.060000 | 3.570000 | -0.166667 |
| poor_quality | insufficient_quality | Not computed | Not computed | Not computed | Not computed |

These values verify intentionally constructed software cases. They do not estimate research accuracy, stress detection or recovery efficacy.

### Optional video adapter

- MediaPipe 0.10.35, OpenCV contrib 5.0.0.93, NumPy 2.5.4, Python 3.12.
- Official Face Landmarker task asset downloaded for a temporary native smoke test; not distributed in the ZIP.
- The environment initially lacked `libGLESv2.so.2`. For verification only, the official Ubuntu `libgles2` package was extracted into a scratch directory and provided through a process-local library search path. No system dependency installation is needed for the core API. Normal Linux users can install EGL/GLES with the commands in `docs/VIDEO_ADAPTER.md`.
- Native smoke test on a generated blank 15-second clip: **passed**. The task loaded on CPU, video decoded and six no-face windows were emitted. No camera or participant data was used.
- Eye geometry, blendshape mapping, pose helpers, head-motion aggregation and multi-face window handling are tested with constructed numerical fixtures.

### Not yet established

No real face recording was evaluated, and no camera/phone frontend was connected. Face-feature accuracy, device robustness, reference stability and relationships with self-report remain to be measured. Windows/macOS setup commands are supplied but were not executed here. The code provides a research prototype, not production participant authentication or validated wellbeing assessment.
