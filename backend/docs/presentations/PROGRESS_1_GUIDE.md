# Progress Presentation 1 — all four baseline backends

## What is completed

A shared FastAPI/SQLite backend provides authenticated development APIs, consent/source records, migrations, histories, model registry, export/deletion and four API-backed browser demonstrations. All are research prototypes, with different data and validation scopes.

| Component | Implemented baseline | Delivered data/evidence | Demo |
|---|---|---|---|
| 1 | Quality-gated personal median/MAD reference, deviation and within-session temporal change | Synthetic numerical fixtures; software checks, no wellbeing training | `/` |
| 2 | eGeMAPSv02 features + public-audio logistic classifier | Original RAVDESS acted speech; held-out actor evaluation | `/voice-demo` |
| 3 | Longitudinal ingestion, point-in-time 14-day features, exploratory exhaustion-proxy random forest | Synthetic-only training/evaluation; no synthetic score assigned to real local records | `/risk-demo` |
| 4 | Generic, preference and feedback-adaptive deterministic activity ranking | Original six-activity catalog; synthetic comparisons and API lifecycle checks | `/interventions-demo` |

Use `docs/COMPONENT_1_FACIAL.md`, `COMPONENT_2_VOICE.md`, `COMPONENT_3_RISK.md` and `COMPONENT_4_INTERVENTIONS.md` for exact algorithms, dataset requirements, API details and separate presentation questions. Show `/api/v1/models` with provenance/validation fields intact. Test success establishes software behaviour, not psychological or clinical validity.

## Suggested 8-minute team demonstration

1. **0:00–0:45 — Research question and architecture.** Introduce the voluntary workflow: check-in, longitudinal records, optional activity and feedback. Explain that C1–C3 outputs are not automatically interpreted as clinical need; C4 currently uses explicit user preferences/context and earlier feedback.
2. **0:45–2:00 — C1.** Open `/`, run the synthetic calibration/check-in demonstration. Show accepted/rejected quality and positive/negative/not-measurable temporal outputs. A large visual deviation is a measurement, not a stress diagnosis.
3. **2:00–3:15 — C2.** On `/voice-demo`, upload a bundled attributed public WAV. Show actual acoustic extraction and model output, including possible disagreement with the acted label. Public acted-speech performance does not establish local-student emotion or wellbeing accuracy.
4. **3:15–4:30 — C3.** On `/risk-demo`, ingest a synthetic profile and show available features/target window, then a sparse case without a score. Explain forecast-time cutoffs, missingness and synthetic-only model scope.
5. **4:30–6:00 — C4.** Register and save preferences on `/interventions-demo`; compare generic and preference options, select one activity, complete it and enter a low simulated rating. Request new adaptive options and show the feedback term. Compare with no eligible activity at one minute. State that immediate completion is a demo event and not verified adherence.
6. **6:00–7:00 — Engineering evidence.** Show `/docs`, registry, histories and participant export. Mention 87 passing tests and real HTTP verification covering all four components. Explain immutable retries, database-upgrade preservation and source separation.
7. **7:00–8:00 — Next milestone.** Connect the team's real frontend and target-device capture, add participant-scoped access for real deployment, collect approved local labels/interactions and evaluate prespecified research questions. No clinical effectiveness or generalization claim has yet been validated.

## Component 1 positioning

Present personal-reference comparison, quality-aware temporal measurements and self-report validation as the research hypothesis. The claimed benefit of that combination needs to be tested. Renaming a generic face classifier does not establish novelty. Three recordings are a technical minimum for the demonstration, not a sufficient calibration or sample-size claim. A quiet protocol phase is labelled “recovery” only as a sequence phase; the metric describes movement towards/farther from the visual reference, not psychological recovery.

## Component 4 positioning

The proposed contribution is an auditable, consented preference/feedback loop in the study's student workflow. Its novelty is not a claim to invent weighted ranking or to deploy reinforcement learning. Compare generic versus preference to test declared preferences, and adaptive versus preference to test the additional feedback term. Report engagement, response rate and perceived helpfulness with missingness; do not report simulation scores as human benefit.

## Scope to state clearly

C1 has no trained wellbeing classifier. C2 has a trained public acted-emotion classifier. C3 has a real sklearn artifact trained entirely on simulated people and an optional source-matched local fitting path. C4 is a fixed deterministic policy with a bounded feedback summary, not a trained neural/bandit model. None is a validated burnout diagnostic model.

No real student dataset, local-student performance, measured intervention efficacy, passive surveillance, camera HRV, LMS integration, therapist replacement or production participant-authentication is included. Refer to `VERIFICATION.md` for executed checks and remaining integration/validation work.
