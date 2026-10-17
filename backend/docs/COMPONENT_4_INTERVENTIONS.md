# Component 4 — Interventions: preference and feedback recommendations

This release implements a low-cost, auditable recommendation backend and an API-backed browser demonstration. It compares **generic rules**, **preference ranking** and **feedback adaptation** over an original six-activity catalog. It runs on a normal CPU with SQLite and needs no paid service, GPU, downloaded dataset or separately trained model.

The research contribution to investigate is whether explicit student constraints, preferences and feedback make optional activities more acceptable or useful than a generic list. The scoring formula is an engineering baseline, not a novel neural architecture, therapy system, contextual bandit or proven burnout intervention. Novelty must be supported by your literature review and subsequent study.

## Run it

Install and start the backend as described in the [project README](../README.md). Then, from the `backend/` folder with the Python 3.12 environment activated:

```bash
python -m pip install -r requirements-tested.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000/interventions-demo>. Keep the default key `local-demo-key-change-me` only for this local synthetic demonstration, or enter your configured key. Register a synthetic participant, save preferences, request options, choose one, mark it completed or abandoned, and optionally submit a simulated helpfulness rating. Request new options to inspect the changed explanation. A different score does not guarantee a different top activity.

The page supplies an elapsed timer and catalog instructions. It does not supply or record audio, collect journal text, verify adherence or implement therapy. Immediate completion is permitted for a progress demonstration, and is labelled an unverified user event. The API, not the timer, controls session state.

CLI demonstration, in a second activated terminal while the server runs:

```bash
python -m scripts.run_interventions_demo
```

The script creates a new synthetic participant, compares the three policies, completes one activity, submits a low simulated rating, and checks the next explanation. It writes `data/interventions_demo_results.json`. Pass `--api-key YOUR_KEY` and/or `--base-url http://127.0.0.1:8001` when needed.

## What the model does

The baseline is a deterministic recommender. It does not require fitting from data. It first removes ineligible activities, then scores the remaining catalog and returns at most the requested number of options.

| Policy | Scoring rule | Purpose |
|---|---|---|
| Generic | `B` | Context-based reference without like/feedback terms |
| Preference | `0.55 B + 0.45 P` | Test the contribution of declared category preferences |
| Adaptive | `0.55 B + 0.25 P + 0.20 H - R` | Test incremental value of prior same-person feedback and a repetition penalty |

Definitions:

- `B = 0.7 G + 0.3 (1 - duration_seconds / available_seconds)`; `G` is 1 if the chosen goal appears in the activity's goal list, otherwise 0. The small duration term favours shorter activities within the available time.
- `P = (category_rating - 1) / 4`; a missing category has neutral rating 3, so `P=0.5`.
- `H = (1.5 + sum((helpfulness - 1)/4)) / (3 + n)`. This shrinks the observed average towards 0.5 with three provisional prior observations. It is a smoothed preference score, not a clinical probability or calibrated Bayesian health estimate.
- `R = 0.05` only for the adaptive policy when this participant started the activity within the previous seven days; otherwise 0. Started activities include subsequently abandoned sessions. Abandonment affects repetition only, not helpfulness.

Only ratings from completed sessions in the last 90 days, at most the most recent 20 per activity, are eligible. Only this participant's source-matched feedback is used. Feedback after the recommendation time is excluded. A newly completed but unrated activity leaves `H` unchanged. `would_repeat` is recorded for descriptive evaluation; it is not currently a second ranking signal. Tie-breaking is by activity ID ascending after rounding scores to eight decimal places.

**All three policies respect the same hard constraints:** explicit activity exclusions; available time; maximum preferred duration; movement disabled; audio disabled. Preferences default to neutral category ratings, movement/audio permitted and a 600-second maximum until explicitly saved. Preference updates replace the preference set using defaults for omitted fields; they are not partial patches.

Weights, prior size, windows and repetition penalty are fixed provisional settings. No tuning on this simulation or human outcomes was performed. Scores are not displayed as health-benefit percentages.

## Catalog

| ID | Activity | Category | Seconds | Goals | Requirement |
|---|---|---|---:|---|---|
| quiet_pause | A quiet pause | pause | 90 | rest, refocus | Seated option |
| screen_break | Step away from the screen | pause | 120 | rest, refocus | Seated option |
| comfortable_walk | An optional short walk | movement | 300 | rest, refocus | Movement permitted |
| next_small_step | Choose one small next step | planning | 180 | organize, refocus | Seated option |
| private_reflection | A private reflection | reflection | 180 | reflect, organize | Notes stay with user |
| chosen_audio | Listen to something you choose | audio | 300 | rest, reflect | Audio permitted; user supplies own player |

Instructions are original, versioned application content, not a copied intervention dataset or evidence-based treatment protocol. Participants can stop or choose another activity. No wearable, HRV, breath-holding, exercise prescription, medication or generative therapy is implemented.

If nothing fits, the response is `no_eligible_activity` with an empty options list and exclusion reasons. Constraints are never silently relaxed.

## Dataset to collect later

Do not convert public emotion labels or synthetic helpfulness into student outcomes. Public face/speech datasets do not contain the preference/offer/exposure/feedback records this component needs. Its useful local dataset is a time-ordered interaction log with clear denominators and nonresponse.

| Record | Fields | Source/timing |
|---|---|---|
| Participant | Pseudonymous ID, consent version, source | Shared participant API |
| Preference version | Category ratings 1–5; exclusions; movement/audio permissions; max seconds | Explicit input; server time and immutable version |
| Recommendation | Strategy; goal; available seconds; full preference snapshot; offered/ranked activities; score components; excluded items; policy/catalog version | Frozen before choice; server timestamp |
| Activity start | Offered recommendation ID; selected activity; activity content; start preference version | Server start time; one chosen activity per recommendation |
| Terminal event | `completed` or `abandoned`; elapsed server time | One terminal event; completion is a report, not adherence proof |
| Feedback | Completed session ID; helpfulness integer 1–5; would-repeat boolean | Optional, one immutable response; server time |
| Derived evaluation | Offers, starts, completions, abandonment, response rate and respondent mean helpfulness by strategy | Descriptive counts; absent feedback remains missing |

Store pseudonymous records, not journal text or raw biometric files. The API does not accept client-supplied ingestion/start/end/feedback timestamps, avoiding fabricated historical availability. Preference, recommendation, event and feedback retries preserve their original snapshots. Session GETs show current state; a retried start POST returns the original start response.

For a feasibility pilot, use repeated voluntary sessions over several weeks. A 30–50-person study can inform usability/acceptance and missingness, but does not automatically establish effectiveness or supply enough evidence to train a bandit. A supervisor should define the study question, allocation, duration, primary outcome and analysis before human data collection; sample-size justification must follow the chosen design.

## REST API

All endpoints below have prefix `/api/v1/interventions` and require `X-API-Key`. POST bodies require `participant_id`, `data_source` (`synthetic_demo` or `local_research`) and strict boolean `consent: true`. Genuine local writes require `ENABLE_RESEARCH_MODE=true`; all demo pages deliberately generate synthetic records. No longitudinal public-data adapter exists for intervention outcomes.

| Method | Path | Purpose |
|---|---|---|
| GET | `/catalog` | Activities, original instructions and version |
| GET | `/policy` | Three formulas, fixed settings, scope |
| GET | `/evaluation` | Supplied synthetic comparison only |
| POST | `/preferences` | Create immutable preference version with `client_update_id` |
| GET | `/preferences/{participant_id}` | Current preferences/defaults |
| POST | `/recommendations` | Create frozen offer with `client_request_id` |
| GET | `/recommendations/{participant_id}/{recommendation_id}` | Read frozen offer |
| POST | `/sessions` | Start one offered activity with `client_session_id` |
| GET | `/sessions/{participant_id}/{session_id}` | Current session state |
| POST | `/events` | Complete or abandon, using `client_event_id` |
| POST | `/feedback` | Rate completed session, using `client_feedback_id` |
| GET | `/history/{participant_id}` | Paginated preferences/recommendations/sessions/events/feedback |
| GET | `/metrics/{participant_id}` | Descriptive engagement by policy |

Shared `/api/v1/participants/{id}/export` and DELETE include all five C4 tables. An API key controls the entire prototype database; participant ownership checks prevent cross-ID references in bodies but **do not provide participant login or per-user authorization**. Real deployment still needs sign-in/scoped access, TLS and suitable storage protection. SQLite is not encrypted here.

Registration example, then preference request bodies (use Swagger `/docs` or your frontend):

```json
{"participant_id":"DEMO-C4","data_source":"synthetic_demo","consent":true}
```

```json
{
  "participant_id":"DEMO-C4",
  "data_source":"synthetic_demo",
  "consent":true,
  "client_update_id":"preferences-1",
  "category_ratings":{"pause":2,"planning":5,"reflection":4},
  "allow_movement":false,
  "allow_audio":false,
  "max_duration_seconds":300,
  "excluded_activity_ids":[]
}
```

Recommendation request:

```json
{
  "participant_id":"DEMO-C4",
  "data_source":"synthetic_demo",
  "consent":true,
  "client_request_id":"recommendation-1",
  "strategy":"adaptive",
  "goal":"refocus",
  "available_seconds":300,
  "limit":3
}
```

Start request uses a returned recommendation ID and one of its offered activity IDs:

```json
{
  "participant_id":"DEMO-C4",
  "data_source":"synthetic_demo",
  "consent":true,
  "client_session_id":"activity-1",
  "recommendation_id":"REPLACE_WITH_RETURNED_ID",
  "activity_id":"next_small_step"
}
```

Terminal event, then optional feedback:

```json
{
  "participant_id":"DEMO-C4",
  "data_source":"synthetic_demo",
  "consent":true,
  "client_event_id":"completion-1",
  "session_id":"REPLACE_WITH_RETURNED_SESSION_ID",
  "outcome":"completed"
}
```

```json
{
  "participant_id":"DEMO-C4",
  "data_source":"synthetic_demo",
  "consent":true,
  "client_feedback_id":"feedback-1",
  "session_id":"REPLACE_WITH_RETURNED_SESSION_ID",
  "helpfulness":4,
  "would_repeat":true
}
```

Offer expiry is 24 hours. Current constraints are checked again at start, so an older offer cannot override a newly excluded activity. An offer can start only one activity. A session goes `started → completed` or `started → abandoned`, with no second terminal outcome or reopening. A conditional database update guards simultaneous terminal outcomes; unique constraints guard duplicate starts/ratings. Concurrent duplicate writes can return 409; retry the identical request to recover the committed response.

Use fresh client IDs for new operations, retain IDs and identical content for retries. Reusing an ID with different content returns 409. Do not invent a new ID after a timeout until you know whether the old operation committed. GET/read history helps recovery. The demo page keeps pending IDs in memory for unchanged retries, but a page reload resets that convenience state; durable offline synchronization is not implemented.

Useful errors: `activity_not_offered` (422); `preferences_changed`, `recommendation_expired`, `recommendation_already_used`, `session_already_finished`, `completed_session_required`, `feedback_already_recorded` (409); absent/foreign referenced record (404); consent/research disabled (403); invalid key (401). Unknown/extra fields and non-integer ratings are rejected.

## Integration with Components 1–3

The recommendation request optionally accepts `facial_session_id`, `voice_session_id` and `risk_prediction_id`. Each reference must exist, belong to this participant and match provenance. The response logs reference ID and status with `used_for_ranking: false`.

This deliberately supports workflow traceability without equating facial deviation, acted speech emotion or a simulation-trained exhaustion score with a student's clinical need. C4 currently ranks by explicit goal/time/preferences/feedback. There is no multimodal health-score fusion, automatic treatment or measured closed-loop health improvement. A frontend can display check-ins alongside this voluntary activity flow while retaining each component's limitations.

## Actual delivered simulation results

Reproduce without downloading a dataset:

```bash
python -m training.evaluate_interventions
python -m training.plot_interventions_evaluation
```

`models/interventions/evaluation.json` contains the complete comparison and assumptions. The generated interaction log goes to `data/synthetic/intervention_interactions.json` and is reproducible rather than bundled. `policy_comparison.png`/`.pdf` can be used on a presentation slide with the synthetic-only label intact.

120 simulated people × 28 decision contexts, seed 418; fixed formulas and common synthetic preferences/contexts/potential responses across policies. Each policy sees only its own earlier observed feedback. There are no human participants. All first offers are assumed started; the simulator independently samples completion and rating response. Hidden random likes, a goal term and noise generate helpfulness; partly missing/noisy declarations provide imperfect preferences. The simulator favours category matching by construction and does not validate human behaviour.

| Policy | Eligible starts | Completed | Observed feedback | Mean simulated respondent helpfulness, 1–5 |
|---|---:|---:|---:|---:|
| Generic | 2,718 | 2,378 | 1,944 | 3.276 |
| Preference | 2,718 | 2,393 | 1,959 | 3.426 |
| Adaptive | 2,718 | 2,375 | 1,939 | 3.407 |

Each policy has 642 contexts with no eligible activity and zero hard-constraint violations. Preference ranking slightly exceeds adaptation in this one simulation. **Do not claim adaptive superiority, real-student accuracy, reduced burnout, statistical significance or clinical effectiveness.** The comparison establishes reproducibility and exercises cold starts, exclusions, missing ratings and feedback accumulation.

The runtime metrics endpoint reports actual database counts by policy, not simulated expected outcomes. Completion rate denominator is started sessions, including still-open ones; feedback response denominator is completed sessions. The endpoint returns null means when there are no ratings, rather than treating nonresponse as a bad rating. Self-selection, context differences and respondent bias prevent causal claims.

## Evaluation plan and future bandit extension

Appropriate first research questions:

1. Do preference constraints eliminate unwanted/infeasible suggestions without making the list unusably small?
2. Are offered activities accepted and completed, and how often is helpfulness feedback provided?
3. Under a prespecified human comparison design, does preference ranking improve perceived relevance over generic rules?
4. Does the bounded feedback term add useful personalization beyond declared preferences, including for new/rarely rated activities?

Report exclusion rate, offer-to-start rate, completion/abandonment, feedback response, mean/median helpfulness among responders, would-repeat, usability and latency. Keep missingness visible. For inferential comparisons, use an approved randomized/counterbalanced design and participant-aware analysis; do not count repeated interactions as independent people. Compare adaptive minus preference, not only adaptive minus generic, to test the feedback contribution.

A contextual bandit is future work. The current deterministic logs have no valid action propensities and no support for every unchosen action; choosing among shown options also introduces participant choice. Naively scoring alternate policies on these selected outcomes is not unbiased offline evaluation. A future study would need appropriate randomized logging, recorded selection probabilities and suitable analysis. There is **no IPS/replay estimator or clinical policy learning in this release**.

Primary background for that future issue: Li, Chu, Langford and Wang, *Unbiased Offline Evaluation of Contextual-bandit-based News Article Recommendation Algorithms*, https://arxiv.org/abs/1003.5956. This is a methodological reference from news recommendation, not evidence that these student activities work or that our implementation is a bandit.

## Progress Presentation 1 talk track

> “We have implemented an explainable activity recommender with generic, preference and feedback-adaptive baselines. Preferences and prior ratings are time-stamped and source-separated. Users choose from eligible activities, and the system records starts, completion or abandonment, and optional feedback. The demo and comparison data are synthetic; we have verified the software, not intervention effectiveness. The next milestone is frontend integration and an approved feasibility study with genuine interaction data.”

Show `/interventions-demo`, select generic then preference with planning rated highly, and point to the different ranking reasons. Complete one activity, give a low demo rating and show its feedback term/repetition penalty in a new recommendation. Show no-options at one minute and excluded movement/audio. Open `/docs` to show stored history, exports and the registry's explicit validation flags.

Likely panel questions:

- **What is trained?** C4 has no pretrained model. It is a deterministic, versioned scoring baseline with smoothed same-person feedback; C2 and C3 have their separate trained artifacts/scopes.
- **Where is the novelty?** The proposal investigates consented constraint-aware, feedback-aware recommendation in this study's student workflow, with transparent explanations and missingness. Establish the gap through literature; do not claim the weighted formula is unprecedented.
- **Why not reinforcement learning now?** We do not yet have suitable local interaction/outcome data or randomized logs. The implemented baselines are feasible and evaluable before policy learning.
- **Did it reduce burnout?** No claim is made. Initial outcomes are feasibility, engagement, preference fit and perceived helpfulness; long-term clinical benefit requires a different study.
- **Is completion true adherence?** No. It is an explicit user event, with server elapsed time reported separately.

## Files and verification

`app/interventions/` contains the catalog, schemas, pure policy, service and REST API. Migration `0004` adds five C4 tables; earlier C1/C2/C3 records remain intact. `app/static/interventions.html` calls the actual API. `scripts/run_interventions_demo.py` exercises the lifecycle. `training/evaluate_interventions.py` supplies the transparent simulator. Tests cover math, temporal bounds, hard constraints, immutable retries, state transitions, source/ownership, export/deletion and migration preservation. See `VERIFICATION.md` for the latest checks and limits.
