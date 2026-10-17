"""Copy three attributed, untouched public test-speaker WAVs into the release."""
import hashlib
import json
import shutil
from pathlib import Path

from training.download_ravdess import CITATION
from training.train_voice import parse_name


def main():
    folder = Path("app/static/voice_samples")
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for emotion in ("01", "03", "05"):
        filename = f"03-01-{emotion}-01-01-01-19.wav"
        source = Path("data/public/ravdess/Actor_19") / filename
        shutil.copyfile(source, folder / filename)
        label, actor = parse_name(source)
        rows.append({"filename": filename, "dataset_recording_id": source.stem, "actor": actor,
                     "dataset_label": label, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                     "training_member": False, "test_member": True})
    manifest = {"dataset": "RAVDESS", "source": "https://zenodo.org/records/1188976", "license": "CC-BY-NC-SA-4.0", "citation": CITATION,
                "modifications": "None; original WAV files copied unchanged.", "purpose": "public-acted-audio technical demo; not independent evaluation", "samples": rows}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Prepared three attributed held-out-speaker public WAV samples.")


if __name__ == "__main__":
    main()
