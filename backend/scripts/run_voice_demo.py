import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx


def run_voice_demo(client, participant_id=None):
    participant_id = participant_id or f"RAVDEMO-{uuid4().hex[:12]}"
    response = client.post("/api/v1/participants", json={"participant_id": participant_id, "data_source": "public_dataset", "consent": True, "consent_version": "RAVDESS-CC-BY-NC-SA-4.0"})
    response.raise_for_status()
    folder = Path(__file__).resolve().parents[1] / "app/static/voice_samples"
    manifest = json.loads((folder / "manifest.json").read_text())
    results = []
    for sample in manifest["samples"]:
        metadata = {"participant_id": participant_id, "client_session_id": sample["dataset_recording_id"], "data_source": "public_dataset", "consent": True,
                    "dataset": "RAVDESS", "dataset_recording_id": sample["dataset_recording_id"]}
        response = client.post("/api/v1/voice/checkins", data={"metadata": json.dumps(metadata)}, files={"audio": (sample["filename"], (folder / sample["filename"]).read_bytes(), "audio/wav")})
        response.raise_for_status()
        results.append({"sample": sample, "response": response.json()})
    history = client.get(f"/api/v1/voice/history/{participant_id}")
    history.raise_for_status()
    return {"participant_id": participant_id, "data_source": "public_dataset", "results": results, "history_total": history.json()["total"],
            "note": "These three files are illustrative members of the public held-out test set; this demo is not a new evaluation."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", "local-demo-key-change-me"))
    parser.add_argument("--output", type=Path, default=Path("data/voice_demo_results.json"))
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, headers={"X-API-Key": args.api_key}, timeout=60, trust_env=False) as client:
        report = run_voice_demo(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for result in report["results"]:
        response = result["response"]
        print(f"Dataset label={result["sample"]["dataset_label"]}; prediction={response["prediction"]["predicted_emotion_style"] if response["prediction"] else "not computed"}; quality={response["status"]}")
    print(f"Stored {report["history_total"]} voice records. Saved {args.output}")


if __name__ == "__main__":
    main()
