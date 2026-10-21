# EMPath+ — Component 4 integration update

This package contains the complete Python backend and Expo mobile app. Component 4 now combines its own recommendation policy with **optional** completed C1–C3 results. It works immediately without running any other assessment. New context mappings are enabled for **synthetic demonstrations only** in this release.

## 1. What changed

| Area | Implemented change |
|---|---|
| Ranking | New `multimodal_weighted` strategy, alongside unchanged Generic, Preference and Adaptive formulas |
| Missing assessments | Missing, rejected, stale or incompatible results have zero weight; remaining weights are renormalized |
| Independent operation | With no eligible context, the new strategy returns exactly the existing Adaptive scores for the same catalog/preferences/history |
| C1–C3 integration | Read-only adapters consume saved outputs; their models, training files, APIs and mobile screens are unchanged |
| Synthetic demonstration | All eight availability combinations can be selected inside Activities; fixtures are stored separately in C4 |
| Explanations | Frozen context IDs, eligibility reasons, weights, mapping version and per-activity score contributions |
| Activities | Eight options, including a one-minute surroundings pause and a two-minute desk reset; each has three timed guide steps |
| Mobile player | Begin, pause, resume, next step, progress, completion and stopping; optional private notes for planning/reflection |
| Recovery | Saved preferences, unfinished activities, earlier unrated completions and recent activity history |
| Retry handling | A pending C4 write is saved before transmission; the exact ID/payload can be retried after a lost response or app reload |
| Database | Additive migration `0005` creates only `intervention_demo_contexts`; integration explanations remain in the existing recommendation JSON |

## 2. Run on Windows

Install **Python 3.12**, Node.js 20+ and a compatible Expo Go version. The project remains on **Expo SDK 57**, as supplied. It has no additional mobile packages. Model artifacts are included: no model training or dataset download is needed for this update.

Extract the ZIP to a new folder. Open Command Prompt in its `academic-burnout` folder.

```bat
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-tested.txt
copy .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If `py -3.12` is unavailable, install Python 3.12 first and check `py -0p`. The existing saved C2/C3 artifacts enforce their dependency versions. Do not replace them with a different Python/model environment merely to bypass a model warning.

In a second Command Prompt, from the extracted project folder:

```bat
cd mobile
npm ci
npx expo start -c
```

## 3. Run on macOS

Install Python 3.12 and Node.js 20+ using your normal installer/package manager. In Terminal, from the extracted project folder:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-tested.txt
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In a second Terminal, from the extracted project folder:

```bash
cd mobile
npm ci
npx expo start -c
```

### Upgrading an existing installation

Stop the backend and back up `backend/data/empath.db` and your `.env` first. Use this updated source tree, preserve your existing `.env` and database, activate your Python environment and run `python -m alembic upgrade head`. It upgrades revision 0004 to 0005 without replacing earlier tables or observations. **Do not delete your database.** Run `python -m alembic current` to confirm 0005. Offers from the older activity catalog may require requesting new options; existing sessions retain their saved instructions.

The normal API version is now **0.5.0**. The health endpoint should return `status: ok`, `voice_model: ready` and `risk_model.status: ready`. Visit `http://127.0.0.1:8000/docs` for Swagger.

## 4. Connect the phone

1. Keep the phone and computer on the same reachable Wi-Fi/hotspot network.
2. Find the computer's active LAN IPv4: Windows `ipconfig`; Mac `ipconfig getifaddr en0` (or inspect the active adapter).
3. In the mobile Profile tab, use `http://YOUR_COMPUTER_IP:8000` and the API key in `.env`. Use your current address, not an old address from a previous hotspot session.
4. Give demo consent and tap **Connect and register**. Stay in **Demo** mode for the new weighted scenarios. `ENABLE_RESEARCH_MODE=false` is sufficient.
5. Open **Activities**. There is no need to open Facial, Voice or Diary first.

If connection fails, open `/health` from the phone browser, check the active adapter/IP and allow Python on your private-network firewall. Do not enter `127.0.0.1` as a physical phone's backend address. C4 does not require camera/microphone permissions.

## 5. Demonstrate independent operation

1. Use a newly registered synthetic participant, or open Synthetic comparison and load the **None** scenario.
2. Choose **Refocus**, **5 min** and **Show options**.
3. Expect **Activities work on their own**. Missing components have zero influence. Recommendations still appear.
4. Open **Why this ranking**: context share is 0%, and no component contribution appears.
5. Compare **Adaptive** and **Optional context** with the same preferences, goal/time and unchanged history. Scores are identical when no result is eligible.

The server resolves results at recommendation time; a preview shown earlier is not a guarantee that an old assessment remains fresh.

## 6. Demonstrate optional integration

1. Expand **Synthetic comparison → Try optional component scenarios**.
2. Choose **All three**, with C1 **Persistent**, C2 **Sad**, C3 **Higher**.
3. Tap **Load synthetic scenario**, then **Show options**.
4. Expect three simulated-result labels. Open **Context weights**: C1 30%, C2 20%, C3 50% **of the context contribution**.
5. Inspect a recommendation's explanation: its own score and component contributions are shown separately. Context occupies 25% of the total blend; C4 retains 75%.
6. Repeat with **C1 + C3**. Expect C1 37.5%, C3 62.5%, C2 0% of context.
7. Repeat with one component, then **None**. A single eligible component gets the full context portion; None returns to independent operation.
8. Choose **Poor quality** for C1/C2 or **Insufficient history** for C3. Those simulated results are excluded. If all are unusable, recommendations still work independently.
9. Turn **Use available check-ins** off: new recommendations ignore context.

Changing selections does not change a loaded fixture until you press **Load synthetic scenario** again. Fixtures expire after 30 minutes and are used only when the app explicitly references their ID. Reloading the app clears this temporary fixture selection. They are never auto-selected just because a fixture exists in the database.

### A visible ranking-change example

On a fresh synthetic participant with no activity history, set Planning preference to **4** and leave the other categories at **3**; save preferences. Choose Refocus and 5 minutes. Load the All three scenario with Persistent/Sad/Higher. Compare strategies before starting any activity: **Adaptive** puts **Choose one small next step** first; **Optional context** puts **A quiet pause** first. The different scores are explained in the response. Earlier feedback, restrictions or repetition history can change this example, so use a fresh participant for a reproducible presentation.

### Using completed results from the other tabs

Choose **Use actual completed demo check-ins instead**, or start without a fixture. Complete a C1 demo check-in within 30 minutes or obtain a C3 demo prediction within 24 hours; return to Activities and request fresh options. The backend reads those saved results automatically. Calibration alone is not a C1 check-in. A rejected capture or a C3 result with no score is not usable.

The supplied Voice demo uses public RAVDESS audio under a **different public-dataset participant**. It is intentionally not attached to your synthetic participant. Use the C4 synthetic voice scenario to demonstrate C2 weighting; the automated adapter test also exercises generated synthetic audio through the actual C2 pipeline. Do not relabel a public recording as a synthetic observation.

## 7. Test the improved activities

1. Choose an offered activity and tap **Start guided activity**.
2. Tap **Begin guide**. Expect a timer, progress bar and current step.
3. Try **Pause guide**, **Resume guide** and **Move to next step**. Leaving the Activities tab or backgrounding pauses the guide. **Return to activities** pauses the guide without recording completion or abandonment; its unfinished session can be resumed.
4. Return after an app reload: **Continue an activity → Resume activity** restores the server session and saved guide progress. Resume the timer explicitly.
5. Planning/reflection activities offer a private note. It is not sent to the API, not persisted, and clears when you leave the activity/tab. The audio activity uses your own audio player; the app does not supply playback.
6. Tap **I completed it**, choose a helpfulness rating and Yes/No, then **Send feedback**. Expect a saved confirmation. You may complete before the timer finishes: completion remains user reported.
7. Alternatively choose **Stop without completing**. Expect an abandonment record and no helpfulness rating.
8. Skip a completion rating: expect **No rating was submitted**, rather than a false saved-feedback confirmation. You can rate an earlier completion later.
9. Save movement/audio restrictions, duration limits or activity exclusions, then request new options. Excluded activities must never return, even when context favours their category.

If an activity is unfinished, resume and complete/stop it before requesting more options. A pending network write has **Retry saved request** and **Clear pending request and refresh** controls. Clearing a pending request does not undo a successful server write; refresh restores server state.

## 8. How the algorithm works

First apply all hard filters: time, duration preference, activity exclusion, movement permission and audio permission.

For every remaining activity:

```text
B = 0.7 × goal_match + 0.3 × (1 − duration / available_time)
P = (category_rating − 1) / 4
H = (1.5 + sum((helpfulness − 1) / 4)) / (3 + number_of_ratings)
U = 0.55 × B + 0.25 × P + 0.20 × H
R = 0.05 if started within the last seven days, otherwise 0

temporary_weight[j] = base_weight[j] × available[j] × reliability[j]
alpha[j] = temporary_weight[j] / sum(temporary_weights)
M(activity) = sum(alpha[j] × compatibility[j, activity_category])

S(activity) = (1 − lambda) × U + lambda × M(activity) − R
```

Base weights: C1 `.30`, C2 `.20`, C3 `.50`. `lambda=.25` if any eligible result exists, otherwise `lambda=0` and `S=U−R`. Reliability is 1 after the technical eligibility checks, otherwise 0; it is not an invented model-confidence probability. The repetition adjustment is applied once. Ties resolve by activity ID after rounding scores to eight decimal places.

Only same-participant, same-source, already available results can contribute. Accepted C1/C2 check-ins expire for weighting after 30 minutes; C3 uses a 24-hour cutoff age. These are provisional protocol settings. All results must precede the recommendation, including capture completion. A valid C1 baseline and compatible versions are required; a C3 abstention contributes nothing. The latest eligible saved assessment is selected from a bounded recent scan unless explicit references are supplied.

### Synthetic compatibility map

Compatibility is an activity-fit test value between 0 and 1. It is not a fatigue score or a predicted health benefit.

| Simulated pattern | Pause | Movement | Planning | Reflection | Audio |
|---|---:|---:|---:|---:|---:|
| C1 persistent visual deviation with little measured return | .8 | .5 | .2 | .5 | .5 |
| C1 stable/returned visual pattern | .5 | .5 | .5 | .5 | .5 |
| C2 sad acted-style fixture | .7 | .5 | .4 | .6 | .6 |
| C2 other acted-style fixture | .5 | .5 | .5 | .5 | .5 |
| C3 higher synthetic exhaustion proxy | .7 | .5 | .3 | .5 | .5 |
| C3 lower synthetic proxy | .5 | .5 | .5 | .5 | .5 |

Mappings are explicit hypotheses to review and evaluate; the implementation does not establish that facial changes or an acted voice label indicate a person's feelings. Real/local participants currently receive independent C4 ranking while this mapping evaluation remains synthetic.

## 9. APIs

Every `/api/v1` route uses the existing `X-API-Key` header.

| API | Purpose |
|---|---|
| `GET /interventions/catalog` | Eight activities, summaries, guide steps and note prompts |
| `GET /interventions/policy` | Formulas, versions, weights, mapping table and freshness settings |
| `GET /interventions/context/{participant_id}` | Preview available source-matched assessment results; optional `demo_context_id` query |
| `POST /interventions/demo-contexts` | Save an explicit C4-only synthetic fixture; synthetic participants only |
| `GET /interventions/state/{participant_id}` | Preferences, unfinished sessions, unrated completions and recent history |
| `POST /interventions/recommendations` | Existing endpoint plus `strategy=multimodal_weighted`, `context_mode` and optional `demo_context_id` |
| `POST /interventions/preferences` | Save ratings, exclusions and permissions |
| `POST /interventions/sessions` | Start one offered activity |
| `POST /interventions/events` | Record completed or abandoned outcome |
| `POST /interventions/feedback` | One optional immutable rating per completed session |
| `GET /interventions/metrics/{participant_id}` | Descriptive engagement/feedback metrics for all four policies |
| `GET /interventions/evaluation/optional-context` | New reproducible eight-case sensitivity/missingness audit |

Routes above have the `/api/v1` prefix. `context_mode` accepts `latest_eligible`, `explicit_refs` or `none`. Existing optional `facial_session_id`, `voice_session_id`, `risk_prediction_id` fields still work. Explicit foreign/mismatched references are rejected; ordinary absence/staleness yields fallback. A synthetic fixture and real assessment references cannot be mixed in one request. Client-supplied weights/raw risk values are not accepted.

Example recommendation body after registering a synthetic participant:

```json
{
  "participant_id": "MY-DEMO",
  "data_source": "synthetic_demo",
  "consent": true,
  "client_request_id": "offer-unique-001",
  "strategy": "multimodal_weighted",
  "goal": "refocus",
  "available_seconds": 300,
  "context_mode": "latest_eligible",
  "limit": 4
}
```

Recommendation responses include `integration` with normalized weights, per-component reasons and source record IDs. Each option's `explanation.component_contributions` records the score calculation. Responses are saved snapshots: retrying the identical request returns the original result even after new assessments arrive or a fixture expires. Use a new request ID to ask for a new recommendation.

## 10. Database and code map

The shared SQLite database stays at `backend/data/empath.db` unless `DATABASE_URL` is changed. Open it with DB Browser for SQLite or export a participant using the existing API. Never hand-edit production observations. Firebase has not been added in this update; later Firestore migration should preserve participant/source boundaries, timestamps, versions and frozen integration snapshots.

| File | Responsibility |
|---|---|
| `backend/app/interventions/context.py` | Read-only C1–C3 adapters, eligibility, synthetic map and weight normalization |
| `backend/app/interventions/policy.py` | Independent and weighted scoring after hard filters |
| `backend/app/interventions/service.py` | Resolve context, freeze recommendation snapshots, demo fixtures and state restoration |
| `backend/app/interventions/schemas.py` | New strategy and validated context/fixture inputs |
| `backend/app/interventions/router.py` | New C4 context/state/fixture/audit APIs |
| `backend/app/interventions/catalog.py` | Eight activities and timed guide steps |
| `backend/migrations/versions/0005_intervention_demo_context.py` | Add the C4-only fixture table |
| `mobile/src/app/(tabs)/activities.tsx` | Activities integration, comparison controls, preferences, history and feedback |
| `mobile/src/components/activity-player.tsx` | Guided activity UI, pause/resume and local progress |
| `mobile/src/lib/activities.ts` | Types, plain-language explanations and persistent exact-request retry |
| `backend/tests/test_interventions_context.py` | Availability masks, actual C1/C2/C3 adapters, failure boundaries and lifecycle tests |
| `backend/training/evaluate_optional_context.py` | Deterministic sensitivity and missingness report |
| `backend/scripts/run_optional_context_demo.py` | Demonstration against a running API |
| `backend/scripts/verify_optional_context.py` | Live HTTP verification with an isolated temporary database |

Shared changes are additive C4 integration: one new ORM table, export/deletion coverage, the 0005 startup check and API version. `backend/app/facial`, `backend/app/voice`, `backend/app/risk`, their model artifacts/training scripts, and the mobile Facial/Voice/Risk screens retain their original architecture and content. See `C4_SOURCE_COMPARISON.json` for the input-archive comparison.

## 11. Reproduce verification

From `backend/`, with the Python environment activated:

```bash
python -m pytest -q
python -m training.evaluate_optional_context
python -m scripts.verify_optional_context
```

The last command launches a temporary local server/database, checks both trained models are ready, runs all eight availability cases and the start/complete/feedback lifecycle, then removes that temporary database. It writes a synthetic report to `data/optional_context_live_verification.json`.

Against your normal running backend instead:

```bash
python -m scripts.run_optional_context_demo
```

This creates a clearly synthetic test participant in your normal database. Supply `--api-key YOUR_KEY` if you changed the development key.

From `mobile/`:

```bash
npm run typecheck
npm run lint
npx expo export --platform web
npx expo export --platform android
```

See `C4_VERIFICATION.md` for the checks actually performed. Bundle export does not replace testing on your physical phone. Use sections 5–7 to rehearse before presenting.

## 12. Research contribution and next stages

The new contribution to test is **whether optional, available multimodal context improves activity selection beyond preferences and feedback while remaining usable when assessments are missing**. It is an explainable decision policy, not a newly trained neural network.

Compare Generic, Preference, Adaptive and Multimodal Weighted using the same eligibility constraints; add C1-only, C2-only and C3-only ablations and controlled missingness. Freeze mapping/weight versions before evaluating. Collect recommendation context, selected activity, completion and optional helpfulness with participant/time separation. Missing feedback is missing, not a zero rating. Current deterministic choices do not provide unbiased counterfactual outcomes.

Next, review compatibility mappings with the supervisor/domain adviser, validate real component signals and run a consented pilot. Later consider a regularized helpfulness model or carefully designed contextual bandit only after enough real interaction data exists. Firebase can make source-matched history available across devices; it does not automatically learn personalization. No claim of reduced burnout or clinical effectiveness is supported by this synthetic implementation.
