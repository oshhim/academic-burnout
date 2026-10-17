import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx

from scripts.risk_demo_data import demo_observations


def run_risk_demo(client):
    results = {}
    for profile in ("steady", "rising", "missing_weekly", "sparse"):
        pid = f"C3-{profile}-{uuid4().hex[:8]}"
        response = client.post("/api/v1/participants", json={"participant_id": pid, "data_source": "synthetic_demo", "consent": True})
        response.raise_for_status()
        daily, weekly = demo_observations(pid, profile)
        response = client.post("/api/v1/risk/daily/batch", json={"records": daily})
        response.raise_for_status()
        for record in weekly:
            response = client.post("/api/v1/risk/weekly", json=record)
            response.raise_for_status()
        response = client.post("/api/v1/risk/predictions", json={"participant_id": pid, "client_prediction_id": "first-prediction"})
        response.raise_for_status()
        results[profile] = response.json()
    return {"data_source": "synthetic_demo", "warning": "All four profiles are constructed software scenarios; they have no real future outcomes or clinical meaning.", "scenarios": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", "local-demo-key-change-me"))
    parser.add_argument("--output", type=Path, default=Path("data/risk_demo_results.json"))
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, headers={"X-API-Key": args.api_key}, timeout=60, trust_env=False) as client:
        report = run_risk_demo(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, result in report["scenarios"].items():
        print(name, result["status"], "simulation score:", result["risk"]["model_probability"] if result["risk"] else "not computed")
    print(f"Saved synthetic demonstration results to {args.output}")
