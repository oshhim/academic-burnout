"""Run against an actual HTTP server: python -m scripts.run_facial_demo."""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx

from scripts.facial_demo_data import calibration_sessions, session


def run_facial_demo(client, participant_id):
    def call(path, payload):
        response = client.post(f"/api/v1/{path}", json=payload)
        if response.is_error:
            raise RuntimeError(f"{response.status_code}: {response.text}")
        return response.json()
    call("participants", {"participant_id": participant_id, "data_source": "synthetic_demo", "consent": True})
    calibrations = [call("facial/calibrations", p) for p in calibration_sessions(participant_id)]
    baseline = call("facial/baselines", {"participant_id": participant_id, "session_ids": [p["session_id"] for p in calibrations]})
    results = {}
    for scenario in ("stable", "return", "persistent", "poor_quality"):
        payload = session(participant_id, scenario, scenario=scenario)
        payload["baseline_id"] = baseline["baseline_id"]
        results[scenario] = call("facial/checkins", payload)
    return {"data_source": "synthetic_demo", "participant_id": participant_id, "baseline": baseline, "scenarios": results}


def main():
    parser = argparse.ArgumentParser(description="Create a unique SYNTHETIC participant and exercise the full C1 API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", "local-demo-key-change-me"))
    parser.add_argument("--output", type=Path, help="Optional JSON output; contains only synthetic results.")
    args = parser.parse_args()
    # Connect directly to the supplied development server, even on computers
    # with unrelated corporate/SOCKS proxy environment variables.
    with httpx.Client(base_url=args.base_url, headers={"X-API-Key": args.api_key}, timeout=20, trust_env=False) as client:
        report = run_facial_demo(client, f"DEMO-{uuid4().hex[:12]}")
    print(f"SYNTHETIC DEMO participant: {report["participant_id"]}")
    for name, result in report["scenarios"].items():
        score = result["deviation"]["mean_absolute_standardized_deviation"] if result["deviation"] else "not computed"
        temporal = result["temporal"]["return_fraction"] if result["temporal"] else None
        print(f"{name:14} status={result["status"]:20} deviation={score!s:12} return_fraction={temporal}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved {args.output}")


if __name__ == "__main__":
    main()

