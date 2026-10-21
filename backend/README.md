> **C4 integration update (v0.5.0):** read [../C4_START_HERE.md](../C4_START_HERE.md) and run `python -m alembic upgrade head` before starting. The latest schema revision is **0005**.

# EMPath+ backend

Part of the [EMPath+ repository](../README.md); the mobile app lives in [`../mobile/`](../mobile/).

Research-prototype backend for EMPath+, with four components behind one FastAPI REST API and one SQLite database:

| Component | What it does | Model | Details |
|---|---|---|---|
| **C1 Facial** | Personal facial-behaviour reference from numerical features (no raw video), deviation and return-towards-reference measurements | Robust statistics; no trained model | [docs/COMPONENT_1_FACIAL.md](docs/COMPONENT_1_FACIAL.md) |
| **C2 Voice** | WAV upload → 88 eGeMAPSv02 acoustic features → acted-emotion style | Logistic regression trained on public RAVDESS speech | [docs/COMPONENT_2_VOICE.md](docs/COMPONENT_2_VOICE.md) |
| **C3 Risk** | Daily/weekly longitudinal observations → point-in-time features → next-week high-exhaustion proxy | Random forest trained on **synthetic data only**; not applied to real records | [docs/COMPONENT_3_RISK.md](docs/COMPONENT_3_RISK.md) |
| **C4 Interventions** | Eight guided activities; independent preference/feedback ranking plus optional availability-weighted synthetic C1–C3 context | Deterministic policy; no trained model | [docs/COMPONENT_4_INTERVENTIONS.md](docs/COMPONENT_4_INTERVENTIONS.md) |

None of these is a validated burnout, stress or clinical model. No GPU, paid API, LLM, cloud account or student dataset is needed: after installing packages, everything runs locally on synthetic data and three bundled public RAVDESS recordings.

Current version: **0.4.0**. See [VERIFICATION.md](VERIFICATION.md) for what was tested and [docs/README.md](docs/README.md) for all documentation.

## Requirements

- **64-bit Python 3.12.** The supplied voice and risk models are pinned to the package versions in `requirements-tested.txt`. Newer Python versions may not install those versions or load the models.
  - macOS: `brew install python@3.12`
  - Windows: install 3.12 from python.org, then use `py -3.12`
- Internet access for the first package install only.

## Setup

Run every command from this `backend/` folder (the one containing `alembic.ini`):

```bash
cd backend
```

**1. Create and activate a virtual environment**

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell (if activation is blocked, use Command Prompt with `.venv\Scripts\activate.bat`, or call `.\.venv\Scripts\python.exe` directly; don't change the system execution policy):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**2. Install dependencies**

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-tested.txt
```

| File | Use |
|---|---|
| `requirements-tested.txt` | Exact versions used for verification. Use this with the supplied models. |
| `requirements.txt` | API runtime, as version ranges |
| `requirements-dev.txt` | Runtime + test tools, as ranges |
| `requirements-training.txt` | Dev + plotting, for retraining |
| `requirements-extractor.txt` | Optional C1 video adapter, in its own environment ([docs/VIDEO_ADAPTER.md](docs/VIDEO_ADAPTER.md)) |

If you upgrade model or extractor dependencies through the range files, retrain the models with those versions.

**3. Create local configuration**

```bash
cp .env.example .env            # Windows: copy .env.example .env
```

For a local demo keep `API_KEY=local-demo-key-change-me` and `ENABLE_RESEARCH_MODE=false`. A changed key must be at least 16 characters, and must also be given to the browser demos, Swagger and CLI scripts. `.env` is git-ignored; never put a real key in frontend code.

**4. Create the database**

```bash
python -m alembic upgrade head
```

This creates `data/empath.db` (git-ignored). The server refuses to start on a missing or out-of-date database, so run this again after pulling new migrations. Migrations only add tables and keep existing data; don't run a downgrade.

## Run

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

| Page | URL |
|---|---|
| C1 facial demo | <http://127.0.0.1:8000/facial-demo> (also `/`) |
| C2 voice demo | <http://127.0.0.1:8000/voice-demo> |
| C3 longitudinal demo | <http://127.0.0.1:8000/risk-demo> |
| C4 recommendation demo | <http://127.0.0.1:8000/interventions-demo> |
| Swagger / API docs | <http://127.0.0.1:8000/docs> |
| Health check | <http://127.0.0.1:8000/health> |

Every `/api/v1` endpoint needs the `X-API-Key` header. In Swagger, click **Authorize** and enter the key from `.env`. Health, the demo pages and the API docs are public on this local server.

What each demo does:

- **C1:** *Run complete demo* creates a synthetic participant, three calibrations, a baseline and four check-ins through the real API. No camera is used.
- **C2:** play a bundled public WAV and click *Analyze and save check-in*. The prediction may disagree with the acted label; draw no wellbeing conclusion from it.
- **C3:** pick a constructed profile and click *Ingest and evaluate*. All profiles and the model are synthetic; the sparse profile correctly returns no score.
- **C4:** register, save preferences, request options, start and finish an activity, rate it, then request options again to see the explanation change.

### Command-line demos

With the server running, in a second terminal (same environment):

```bash
python -m scripts.run_facial_demo --output data/facial_demo_results.json
python -m scripts.run_voice_demo --output data/voice_demo_results.json
python -m scripts.run_risk_demo --output data/risk_demo_results.json
python -m scripts.run_interventions_demo --output data/interventions_demo_results.json
```

Add `--api-key YOUR_KEY` if you changed the key, or `--base-url http://127.0.0.1:8001` for another port.

Expected C1 outcomes (designed synthetic cases for integration testing, **not** research accuracy):

| Scenario | Result |
|---|---|
| stable | Low deviation; no meaningful task increase; return fraction not measurable |
| return | Task deviation rises, then moves back towards baseline; positive return fraction |
| persistent | Recovery-phase deviation exceeds task deviation; negative return fraction |
| poor_quality | No deviation or temporal score; asks for a self-report instead |

Reference outputs are in [examples/facial_http_results.json](examples/facial_http_results.json) (C1) and [examples/all_components_http_results.json](examples/all_components_http_results.json) (all four).

## Test

```bash
python -m pytest -q
python -m scripts.verify_http
```

Tests build throwaway databases through the real migrations and never touch `data/empath.db`. `verify_http` starts a real server on a free port with a temporary database, runs all four components over HTTP, then shuts down.

## Connect a frontend

Use `http://127.0.0.1:8000/api/v1` as the base URL, sending `X-API-Key`. Origins on ports 3000 and 5173 are allowed by default; add others to `CORS_ORIGINS` in `.env` and restart.

For C1: register the participant, send three accepted calibration sessions, create the baseline from the returned session IDs, then send check-ins and self-reports. `python -m scripts.write_examples` regenerates valid sample request bodies in [examples/inputs/](examples/inputs/); in `baseline_template.json`, replace the sample IDs with the session IDs your calibration calls returned. Endpoint and field details for every component are in [docs/](docs/README.md).

**Before any real student data:** the single API key is an administrator key for the whole database, there is no participant sign-in or per-participant authorization, SQLite is not encrypted, and CORS is not authentication. Add sign-in, scoped authorization, TLS and storage protection first, and enable research mode only under ethical approval.

## Retrain models (optional)

The supplied models run without training. To reproduce them:

```bash
# C2 voice: downloads ~209 MB of original RAVDESS speech into data/public/ravdess
python -m training.download_ravdess
python -m training.train_voice
python -m training.plot_voice_evaluation

# C3 risk: synthetic data only
python -m training.generate_risk_data
python -m training.train_risk
python -m training.plot_risk_evaluation

# C4 interventions: synthetic policy comparison
python -m training.evaluate_interventions
python -m training.plot_interventions_evaluation
```

Restart the server after replacing a model. Methods, splits and results are in each component's doc.

## Project layout

```text
app/
  main.py             App factory, middleware, routes, startup checks
  config.py           Settings loaded from .env
  database.py         SQLAlchemy engine and session
  models.py           Database tables (all components)
  schemas.py          Shared request/response schemas
  participants.py     Participant registration, consent, export, deletion
  facial/             C1 calculations, service, router, feature adapter
  voice/              C2 audio validation, eGeMAPS features, model loader, router
  risk/               C3 ingestion, availability-aware features, proxy model, router
  interventions/      C4 catalog, constraint filtering, ranking policy, router
  static/             Demo pages (facial, voice, risk, interventions) and voice samples
models/
  voice/              C2 model, model card, evaluation, dataset manifest, plots
  risk/               C3 synthetic-only model, model card, evaluation, split manifest, plots
  interventions/      C4 policy card, simulation evaluation, plot
migrations/           Alembic schema versions 0001–0004 (one per component)
training/             Dataset download/generation, training and plotting scripts
scripts/              CLI demo clients, HTTP verifier, example writer, video adapter
tests/                Unit, API and migration tests (test_<component>_*.py)
examples/             Sample request bodies and verified HTTP outputs
docs/                 Component docs, video adapter, presentations, history
data/                 Created at runtime: database, datasets, outputs (git-ignored)
```

No real student records, private recordings, images or video are included. The three bundled RAVDESS recordings and C2 model are redistributed with attribution; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named ...` | Activate the `.venv` environment and install `requirements-tested.txt`. |
| Server says to initialize/update the database | Run `python -m alembic upgrade head` from the `backend/` folder, using the same `.env` as the server. |
| HTTP 401 | The key in your client differs from `API_KEY` in `.env`. |
| HTTP 409 `baseline_required` | Register and calibrate that same participant first. |
| HTTP 409 `future_baseline` | The check-in starts before the selected calibration ended. Fix timestamps or use an older baseline. |
| HTTP 409 `extractor_mismatch` | Calibrations and check-ins used different extractor versions. Build a new baseline with one extractor. |
| HTTP 422 | Read the validation response. Windows need chronological timestamps, a 10–180 s session, finite values and valid phases. |
| Browser fetch blocked | Use the same `localhost`/`127.0.0.1` origin as configured, or add it to `CORS_ORIGINS`. |
| Port busy | Start with `--port 8001` and pass `--base-url http://127.0.0.1:8001` to the CLI demos. |
| Voice model unavailable (503) | Install `requirements-tested.txt`, keep `VOICE_MODEL_DIR=models/voice`, and check `model.joblib` and `model_card.json` exist. A dependency, version or checksum mismatch blocks loading. |
| Voice invalid audio (422) | Use WAV, 1–30 s, mono/stereo, 8–96 kHz. WebM/MP3/M4A are not accepted; prefer 16 kHz mono PCM16. |
| Voice insufficient quality | Check signal level and clipping. Silence returns no prediction. |
| Private recordings refused | Expected while `ENABLE_RESEARCH_MODE=false`. Bundled public audio still works. |
| Risk `insufficient_history` | Needs ≥7 prior complete daily reports with ≥7 days of sleep/study/task data and ≥10 available predictor values. Missing data are not zeros. |
| Risk `awaiting_source_matched_model` | Correct behaviour: the bundled model is synthetic-only, so it gives no probability for real local records. History and features still work. |
| Historical risk preview empty after backfill | An observation entered today was not available to yesterday's forecast. Server ingestion time is enforced on purpose. |

Stop the server with Ctrl+C; data persists across restarts.

## Next steps

Connect the team's frontend to these APIs, add participant sign-in and scoped authorization, then collect approved local validation and interaction data. Keep source, quality, cutoff, model/policy version and missingness with every result, and make no clinical-effectiveness claims from the simulations.
