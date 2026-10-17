# Component 3 — Longitudinal risk: ingestion and exploratory model backend

## Status and target

This release implements real database/API processing and a real fitted sklearn model, with **synthetic training data only** in the supplied C3 artifact. Its purpose is to exercise collection, point-in-time features, model loading, comparisons, forecasts and exports before a local study. It does not establish student predictive accuracy.

The target is **an exhaustion rating ≥4 on the next observed weekly assessment within the next seven local calendar days**. The question is a custom exploratory 1–5 item (`exploratory-exhaustion-item-v1`), not a validated burnout instrument. The backend never returns a clinical burnout probability. Optional weekly disengagement and academic-efficacy ratings are exploratory individual items too; they are not an MBI or another copyrighted scale.

The target is observable and testable, but its scientific usefulness remains to be evaluated. Missing future assessments are not assigned a negative label. Training examples are constructed from genuinely observed future assessments (simulated in the bundled dataset). A future outcome is never placed among its own predictors. The fitting procedure creates seven-day-ahead anchors; use weekly forecast issuance in a study and validate other horizons/cadences separately.

## Implemented work

- Strict daily/weekly ingestion with consent, source separation, immutable records, unique date/client IDs, idempotent retries and atomic batches.
- Separate observation date, participant report time and **server-controlled ingestion time**.
- Fourteen complete local calendar days of daily history, latest available weekly assessment from the past 28 days, missingness and calendar-based trends.
- A minimum-history gate, frozen input-record IDs, feature-snapshot SHA-256 and immutable prediction history.
- Dummy-prior/persistence/logistic/random-forest/gradient-boosting comparisons; person-separated, time-purged simulation validation and testing.
- A synthetic-only source guard: real local records receive features but **no synthetic-trained probability**.
- Model/version/checksum/schema/dependency checks; no arbitrary model-upload endpoint and no LLM/API call.
- C1/C2 availability context, shared participant export/deletion, migration 0003, browser and CLI demos, reproducible training and plotting scripts.

## Data to collect in the real study

Register pseudonymous participant IDs using `data_source=local_research`, approved consent and the intended study protocol. Real collection is disabled until appropriately enabled with `ENABLE_RESEARCH_MODE=true`; changing that setting is not ethics approval. Do not put real names, student numbers or raw camera/voice data into C3 fields.

| Frequency | Fields | Meaning/range |
|---|---|---|
| Every observation | participant/client record IDs, source, consent, observed_on, reported_at | Actual assessment/study day and actual report timestamp |
| Daily | sleep_hours | 0–16; missing is null |
| Daily | study_minutes, break_minutes | 0–960 and 0–480 |
| Daily | late_study_minutes | Define a consistent local late-study interval in the protocol; cannot exceed study minutes |
| Daily | planned_tasks, completed_tasks | Both present or both null; 0–50; completed ≤ planned for this task protocol |
| Daily | fatigue, mental_strain, concentration_readiness | Optional integers 1–5; exploratory labels, not diagnoses |
| Weekly | exhaustion | Required integer 1–5; high-exhaustion proxy ≥4 |
| Weekly | disengagement, academic_efficacy | Optional integers 1–5 |
| Server-generated | record_id, ingested_at | Cannot be supplied or backdated by API clients |

Collect a consistent schedule, devices/context and adherence information under the approved study. Record *why* data are missing in the study documentation. Do not replace missing observations with zeros or manufacture extra weeks. Statistical power and an appropriate validated instrument need supervisor/domain guidance; software eligibility thresholds are not sample-size justification.

The task counter schema assumes completed tasks belong to the planned set. If you need unplanned tasks, define and version a separate field rather than exceeding `planned_tasks`. Daily/weekly records are immutable in this release; corrections/revisions require a later audited revision workflow. Do not silently overwrite research records.

## Time and leakage rules

The version-1 study timezone is fixed to **Asia/Colombo**. All incoming timestamps require offsets and are normalized to UTC for storage. If the study timezone or feature semantics change, version/retrain the feature model. `tzdata` is supplied for Windows timezone support.

For a prediction cutoff `as_of`:

1. Derive the local calendar day from the cutoff.
2. Use daily dates from day−14 through day−1. The current incomplete day is excluded.
3. Use a weekly assessment from day−28 through the current local day only if its report and ingestion timestamps are already at/before `as_of`.
4. Require **both** `reported_at <= as_of` and `ingested_at <= as_of` for every input.
5. Freeze the accepted record IDs, missingness, features, model ID and snapshot hash in the stored prediction.

Example: an October 3 diary entered into the server on October 10 can contribute to an October 10 forecast if in the lookback. It cannot appear in an October 5 historical forecast, even if the client supplies an October 3 report time. A retrospective import does not recreate earlier real-time knowledge.

`as_of` cannot be in the future. Omitting it uses server time. Repeating the same participant/client prediction ID with the original request returns the stored snapshot, even after newer records/model versions arrive; use a new ID to make a new forecast. Changing the cutoff while reusing that ID gives HTTP 409.

## Feature definitions and missingness

The 20 schema-ordered predictors are exposed at `/risk/config` and in the model card.

| Group | Predictors |
|---|---|
| Sleep | Mean hours, population standard deviation, calendar-day slope |
| Study | Mean minutes, standard deviation, late-study minutes / eligible total study minutes |
| Breaks/tasks | Mean break minutes; total completed / total planned for days with planned >0; fraction of those days incomplete |
| Coverage | Distinct daily reports /14; days with sleep, study or task observations /14 |
| Daily self-report | Mean fatigue, strain and concentration readiness; fatigue calendar-day slope |
| Weekly self-report | Latest available exhaustion, disengagement and academic efficacy; assessment age in days; explicit missing-weekly flag |

Means ignore null fields; absent days are not zero-valued days. A zero denominator yields null. Slopes use actual day spacing and need ≥3 nonmissing points spanning ≥3 days. Require ≥7 distinct daily reports, ≥7 days with at least one sleep/study/task observation and ≥10 nonmissing predictors. These are provisional engineering gates, not clinical eligibility thresholds.

Missing feature values reach sklearn as NaN and are imputed using **training-fold medians plus missing indicators** inside the pipeline. No scaler/imputer is fitted using test records. Input IDs, data-source labels, participant IDs and future outcomes are not model predictors.

C1 facial deviations and C2 acted-emotion scores are not used as exhaustion probabilities. Their accepted-session availability in the lookback is returned only as context. A later multimodal ablation needs local linked data and an independent evaluation; this release does not claim a validated multimodal improvement.

## Supplied synthetic data/model

The generator simulates 240 people for 98 days, with person differences, a stochastic latent process, exam-like pressure, independent random shocks, missing reports, field missingness and report/ingestion delays. Weekly outcomes depend noisily on the future latent state, rather than being assigned by a threshold on the input feature vector. This improves technical realism but cannot make synthetic data empirically accurate.

- Generator seed 73 and complete simulator source are supplied.
- 2,741 eligible labelled windows; 464 insufficient-history/unused target windows in the supplied run.
- 192 training-cohort people and 48 disjoint held-out people.
- Training examples: 1,276 windows whose labels were already available by March 10, 2025 local end of day.
- Final test: 183 windows from different people, with issuance dates after that cutoff.
- Three training-only CV folds separately withhold people and require training labels to be available before a calendar cutoff; validation issue dates come later.
- Median imputation, missing indicators and any scaling are fitted inside each training fold only.
- Select the learned model by training-CV ROC AUC, freeze selection and then report all final-test comparisons. Do not switch to a test-set winner.

Actual **simulation-only** results:

| Model | Purged CV ROC AUC | Synthetic test ROC AUC | Synthetic test Brier |
|---|---:|---:|---:|
| Dummy prior | 0.5000 | 0.5000 | 0.1678 |
| Prior weekly persistence | 0.7672 | 0.5879 | 0.2514 |
| Behaviour-only logistic | 0.8330 | 0.8157 | 0.1957 |
| Combined logistic | 0.8244 | 0.8109 | 0.1966 |
| Combined random forest — selected | **0.8348** | **0.8077** | **0.1966** |
| Combined gradient boosting | 0.8161 | 0.7874 | 0.1924 |

The selected forest has 120 trees, maximum depth 5, minimum leaf 12 and balanced class weights. These modest fixed settings suit a CPU prototype. The logistic comparisons use C=1 with class balancing. Dummy and persistence are benchmark comparators, not silent production fallbacks.

An independent shifted simulation (seed 947, 80 new simulated people, more noise/missingness) gives selected-model ROC AUC about 0.7925 on 830 windows. This is **another simulator check**, not external human validation. Repeated windows are correlated within people; row counts do not equal independent participants.

ROC AUC measures ranking; Brier measures probability error (lower is better). The selected model's Brier is worse than the dummy prior, so the ranking result does not establish reliable probability calibration even within this simulation. No real-student accuracy, calibration, clinical cutoff or burnout reduction can be claimed from these figures. The behaviour-only test AUC is also slightly higher than the selected combined model; do not claim self-report fusion improved performance on the basis of this run.

Full results, per-fold participant lists, time cutoffs, test predictions, shifted metrics and the train/test/purged manifest are in `models/risk/`. The full generated dataset is not committed (it is written to the git-ignored `data/` folder) and can be regenerated locally; no genuine participant data are supplied.

## Run it

Use 64-bit Python 3.12 and the root README's pinned setup. The trained artifact is included; no training, paid service, GPU or public dataset download is needed for the C3 demo.

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000/risk-demo>. It submits real API calls for constructed steady, rising, missing-weekly and sparse profiles. The first three generate simulation scores; the sparse profile returns no score. They do not have known real future outcomes and must not be used to calculate an empirical accuracy.

With the server running, another activated terminal:

```bash
python -m scripts.run_risk_demo --output data/risk_demo_results.json
python -m pytest -q
```

Self-contained HTTP verification starts/stops a temporary server and checks C1, C2 and C3:

```bash
python -m scripts.verify_http
```

To reproduce the supplied technical model:

```bash
python -m training.generate_risk_data
python -m training.train_risk
python -m training.plot_risk_evaluation
```

Stop/restart the API around replacing/retraining model artifacts. Runtime rejects mismatched schema, checksum or sklearn/NumPy/joblib versions. Load only trusted local model files produced by the training pipeline; joblib files are not safe to accept from untrusted uploads.

## API

All below begin `/api/v1` and require the configured `X-API-Key`. Swagger request schemas are at `/docs`.

| Method | Endpoint | Action |
|---|---|---|
| GET | /risk/config | Protocol, predictor names, gates and target |
| GET | /risk/model | Actual model source/status/card |
| GET | /risk/evaluation | Clearly labelled comparison results |
| POST | /risk/daily | Store one immutable daily report |
| POST | /risk/daily/batch | Atomically ingest 1–90 reports for one participant/source |
| POST | /risk/weekly | Store one weekly assessment |
| GET | /risk/features/{participant_id}?as_of=... | Read-only point-in-time preview |
| POST | /risk/predictions | Store a frozen feature snapshot and eligible proxy result |
| GET | /risk/history/{participant_id}?kind=daily\|weekly\|predictions | Paginated observations/results |
| GET | /participants/{id}/export | Export C1/C2/C3 with original ingestion times |
| DELETE | /participants/{id} | Remove that participant and all three components' records |

Example daily request (replace dates with actual observations; the example is explicitly synthetic):

```json
{
  "participant_id": "DEMO-01",
  "client_record_id": "daily-001",
  "data_source": "synthetic_demo",
  "consent": true,
  "observed_on": "2026-10-15",
  "reported_at": "2026-10-15T21:00:00+05:30",
  "sleep_hours": 7.5,
  "study_minutes": 180,
  "break_minutes": 45,
  "late_study_minutes": 20,
  "planned_tasks": 5,
  "completed_tasks": 4,
  "fatigue": 3,
  "mental_strain": 3,
  "concentration_readiness": 4
}
```

Register the same participant/source first with `/participants`. For a batch use `{"records":[...]}`. Supply missing values as null or omit optional fields; do not use an empty string. Server `ingested_at`/`record_id` are returned, not accepted in incoming observations. Reusing a date or client observation ID with different content gives 409.

Weekly request uses the same common IDs/source/consent/date/report-time fields plus `exhaustion`, optional `disengagement`, `academic_efficacy` and the fixed `instrument_version`. Use one assessment per week as prespecified in your study. The API enforces unique assessment dates but does not enforce exactly seven days between real visits.

Prediction request:

```json
{"participant_id":"DEMO-01","client_prediction_id":"forecast-001"}
```

Optional `as_of` must be timezone-aware and not future. Result statuses:

| Status | Meaning |
|---|---|
| demo_only_prediction | Synthetic inputs and synthetic model; a technical score is returned |
| insufficient_history | Inputs/gates insufficient; risk is null |
| awaiting_source_matched_model | Local observations with only the supplied synthetic model; risk is null |
| model_unavailable | Missing/incompatible artifact; features persist but risk is null |
| exploratory_local_prediction | A separately fitted matching-source local proxy model exists; still not clinically validated |

`risk.model_probability` is explicitly uncalibrated and scoped to its training source; `clinical_risk_probability` is always null. The score/band does not determine treatment or validate a burnout diagnosis. Include quality, source, cutoff, model ID and missingness with any future Component 4 integration.

## Approved local study and future fitting

Actual collection works independently of model fitting. With approved consent and research mode enabled, create `local_research` participants and send real daily/weekly reports when collected. The bundled model will not assign them a synthetic-trained probability; you can still inspect/export history and features.

Save one authenticated participant export JSON per person, then build an offline dataset without changing timestamps:

```bash
python -m training.build_risk_dataset --exports-dir data/local_exports --output data/local/risk_dataset.json
```

There is a separate opt-in local-pilot fitting path:

```bash
python -m training.train_risk --dataset data/local/risk_dataset.json --output models/risk_local --allow-local-research
```

This requires genuine consented data with at least 30 participants and 42 observed calendar days, ≥20 eligible earlier training windows and ≥10 later held-out-person test windows, with both target classes present. These are software checks, **not a power calculation or proof that a six-week pilot will produce a reliable model**. Collection delays/missingness/outcome distribution may make fitting impossible even when those headline counts are met. Four-week or sparse pilots should report feasibility, completeness and descriptive trends rather than generate extra weeks or promise a forecast result.

The small local-pilot path uses a **prespecified combined logistic C=1 model**, not synthetic-CV selection. It holds out people, trains only on labels available before the 52%-of-study calendar cutoff, tests on later issue dates and fits preprocessing on training only. It claims no CV hyperparameter-selection result. It reports comparators after the prespecified model choice; do not select a test winner. Do not interpret a tiny test set as a clinical validation study. A larger or differently scheduled real study should use a supervisor-approved, prespecified evaluation design.

Only after appropriate review of those real results, point `RISK_MODEL_DIR` at the locally fitted artifact and restart. Its source then matches local input, producing an explicitly exploratory local exhaustion proxy; it still does not become a validated burnout assessment. Never relabel synthetic data or the supplied artifact as local research.

## Progress presentation guide

1. Explain the observable seven-day self-report target and the absent clinical validation.
2. Open `/risk-demo`, ingest a profile, inspect the 14-day window, immutable record IDs and snapshot hash.
3. Demonstrate sparse/missing-weekly cases and show the synthetic source warning.
4. Explain the distinction between report time and server availability; show a historical cutoff excluding backfilled records.
5. Present person/time-separated evaluation and correctly labelled simulation plots. Discuss why ranking and calibration differ.
6. Show tests and migration preservation of C1/C2. State that the main next research milestone is actual local longitudinal data, not a larger neural network.

Proposed novelty lies in the availability-aware longitudinal workflow, transparent missingness and integration into the team's feedback study. This implementation does not prove worldwide originality or predictive benefit. Do not claim clinical burnout detection, an original RF architecture, multimodal superiority, real-student accuracy or intervention efficacy from synthetic results.

Technical reference: scikit-learn guidance on training-only preprocessing and leakage: <https://scikit-learn.org/stable/common_pitfalls.html>. The implementation's additional person/time/availability rules are defined above and audited in tests.
