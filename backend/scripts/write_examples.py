import json
from pathlib import Path

from scripts.facial_demo_data import calibration_sessions, session


def main():
    folder = Path("examples/inputs")
    folder.mkdir(parents=True, exist_ok=True)
    payloads = {"participant": {"participant_id": "EXAMPLE-01", "data_source": "synthetic_demo", "consent": True}}
    for i, payload in enumerate(calibration_sessions("EXAMPLE-01")):
        payloads[f"calibration_{i}"] = payload
    payloads["baseline_template"] = {"participant_id": "EXAMPLE-01", "session_ids": ["REPLACE_WITH_RETURNED_SESSION_ID_0", "REPLACE_WITH_RETURNED_SESSION_ID_1", "REPLACE_WITH_RETURNED_SESSION_ID_2"]}
    for scenario in ("stable", "return", "persistent", "poor_quality"):
        payloads[f"checkin_{scenario}"] = session("EXAMPLE-01", scenario, scenario=scenario)
    payloads["self_report"] = {"fatigue": 2, "mental_strain": 3, "concentration_readiness": 4}
    for name, payload in payloads.items():
        (folder / f"{name}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payloads)} synthetic request examples to {folder}")


if __name__ == "__main__":
    main()
