# Component 4 — Optional multimodal activity recommendations

The current release implements **independent activity recommendations with optional availability-weighted synthetic context**. Read the complete [setup, architecture, algorithm, API and mobile testing guide](../../C4_START_HERE.md).

## Current pipeline

1. Apply explicit exclusions, time/duration limits and movement/audio permissions.
2. Compute the existing goal/time, category preference and smoothed past-helpfulness terms.
3. For `multimodal_weighted`, resolve eligible same-participant, source-matched saved C1/C2/C3 results, or a specifically requested C4-only synthetic fixture.
4. Remove unavailable results and normalize the .30/.20/.50 component weights.
5. Blend 75% independent score with 25% mapped context compatibility, then apply the repetition adjustment once.
6. If no result is eligible, use the exact independent Adaptive score and retain all functionality.
7. Persist a frozen recommendation, selected context IDs, reasons, normalized weights, map/policy version and per-option contributions.
8. Track activity start, completed/abandoned outcome and optional immutable helpfulness feedback.

The other components' architectures and models have not been modified. A missing assessment never blocks C4. Mapping is currently enabled only for `synthetic_demo`; real/local recommendations continue independently.

## APIs and mobile

The existing recommendations endpoint adds `multimodal_weighted`, `context_mode` and `demo_context_id`. New C4-only endpoints provide a context preview, synthetic fixture creation, saved activity state and the eight-case evaluation report. All use existing authentication and participant/source checks.

The mobile Activities tab supports all eight component availability masks, quality/history failures, an optional check-in toggle, explanations, saved preferences, per-activity exclusions, history and resumed sessions. Eight activities have three timed guide steps. Private notes are temporary screen state only.

## Evidence and research limits

This is a fixed explainable algorithm, not a trained C4 ML model. Context mappings and weights are provisional engineering hypotheses. Synthetic tests demonstrate operation and missing-data robustness, not effectiveness for real people.

`models/interventions/optional_context_evaluation.json` contains the new availability/sensitivity audit. The older `evaluation.json` and plots concern only the earlier preference-feedback simulator. That simulator has no C1/C2/C3 signals and cannot establish a benefit from the new integration.

Compare all four policies prospectively with real consented activity feedback, along with modality ablations and missingness. A future learned helpfulness model or bandit requires an appropriate interaction dataset and evaluation protocol. See the guide for Firebase migration and future personalization considerations.

The earlier baseline description is retained in [history/COMPONENT_4_BASELINE_V1.md](history/COMPONENT_4_BASELINE_V1.md) as historical documentation.
