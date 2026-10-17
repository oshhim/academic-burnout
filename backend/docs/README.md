# Documentation

Setup and running instructions are in the [project README](../README.md).

## Components

| Component | Code | Document |
|---|---|---|
| C1 — Facial behaviour reference | `app/facial/` | [COMPONENT_1_FACIAL.md](COMPONENT_1_FACIAL.md): input protocol, features, quality gate, robust reference, deviation and temporal formulas, endpoints |
| C2 — Voice | `app/voice/` | [COMPONENT_2_VOICE.md](COMPONENT_2_VOICE.md): RAVDESS dataset, eGeMAPS pipeline, model comparison, retraining, endpoints |
| C3 — Longitudinal risk | `app/risk/` | [COMPONENT_3_RISK.md](COMPONENT_3_RISK.md): data to collect, leakage and missingness rules, synthetic model, endpoints, local fitting |
| C4 — Interventions | `app/interventions/` | [COMPONENT_4_INTERVENTIONS.md](COMPONENT_4_INTERVENTIONS.md): ranking formulas, activity catalog, lifecycle, endpoints, simulation results |

## Other documents

- [VIDEO_ADAPTER.md](VIDEO_ADAPTER.md): optional MediaPipe tool that turns a local video into C1 input JSON.
- [presentations/PROGRESS_1_GUIDE.md](presentations/PROGRESS_1_GUIDE.md): demo script and positioning for Progress Presentation 1.
- [history/VERIFICATION_HISTORY.md](history/VERIFICATION_HISTORY.md): verification records for releases 0.1.0–0.3.0.

## In the backend folder

- [VERIFICATION.md](../VERIFICATION.md): what was tested for the current release, and what was not.
- [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md): dataset and software attribution.
