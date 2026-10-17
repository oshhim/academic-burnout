"""Build offline fitting data from authenticated participant export JSONs."""
import argparse
import json
from pathlib import Path

from app.risk.schemas import STUDY_TIMEZONE
from training.train_risk import validate_dataset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read genuine per-participant API exports; retain original server availability times. Does not fit a model.")
    parser.add_argument("--exports-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    people, sources = [], set()
    for file in sorted(args.exports_dir.glob("*.json")):
        record = json.loads(file.read_text(encoding="utf-8"))
        sources.add(record["data_source"])
        people.append({"participant_id": record["participant_id"], "data_source": record["data_source"],
                       "daily": record["risk_daily"], "weekly": record["risk_weekly"]})
    if not people or len(sources) != 1 or next(iter(sources)) not in {"synthetic_demo", "local_research"}:
        parser.error("Provide non-empty exports from exactly one supported source; do not mix synthetic and local participants.")
    dataset = {"dataset_name": "API longitudinal participant exports", "data_source": next(iter(sources)), "study_timezone": STUDY_TIMEZONE, "participants": people}
    validate_dataset(dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    print(f"Built {len(people)} participant records with original ingestion/report timestamps; saved {args.output}")
