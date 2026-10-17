"""Full RAVDESS speech training; held-out actors never select parameters."""
import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC, SVC

from app.voice.features import FEATURE_SCHEMA, extract_features, extractor_version, feature_names
from training.download_ravdess import CITATION, MD5, URL

LABELS = ["neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"]
TRAIN_ACTORS = list(range(1, 19))
TEST_ACTORS = list(range(19, 25))


def parse_name(path):
    parts = path.stem.split("-")
    if len(parts) != 7 or any(not p.isdigit() for p in parts):
        raise ValueError(f"Unexpected RAVDESS filename: {path.name}")
    modality, channel, emotion, intensity, statement, repetition, actor = map(int, parts)
    if modality != 3 or channel != 1 or not 1 <= emotion <= 8 or not 1 <= actor <= 24 or intensity not in (1, 2) or statement not in (1, 2) or repetition not in (1, 2):
        raise ValueError(f"Not original RAVDESS speech audio: {path.name}")
    return LABELS[emotion - 1], actor


def candidates():
    return {
        "dummy_most_frequent": DummyClassifier(strategy="most_frequent"),
        "logistic_regression_C1": make_pipeline(StandardScaler(), LogisticRegression(C=1, class_weight="balanced", max_iter=3000, random_state=42)),
        "linear_svm_C1": make_pipeline(StandardScaler(), LinearSVC(C=1, class_weight="balanced", max_iter=10000, random_state=42)),
        "rbf_svm_C1": make_pipeline(StandardScaler(), SVC(C=1, gamma="scale", class_weight="balanced")),
        "rbf_svm_C10": make_pipeline(StandardScaler(), SVC(C=10, gamma="scale", class_weight="balanced")),
    }


def metrics(y, pred):
    return {"accuracy": float(accuracy_score(y, pred)), "balanced_accuracy_uar": float(balanced_accuracy_score(y, pred)),
            "macro_f1": float(f1_score(y, pred, labels=LABELS, average="macro", zero_division=0)),
            "confusion_matrix": confusion_matrix(y, pred, labels=LABELS).tolist(),
            "per_class": classification_report(y, pred, labels=LABELS, output_dict=True, zero_division=0)}


def train(dataset, output):
    output.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((dataset / "PROVENANCE.json").read_text())
    if provenance["archive_md5"] != MD5:
        raise ValueError("Use the official verified download script before training.")
    files = sorted(dataset.glob("Actor_*/*.wav"))
    if len(files) != 1440 or len({p.name for p in files}) != 1440:
        raise ValueError("Full baseline requires all 1440 unique original speech WAVs.")
    names = feature_names()
    version_string = extractor_version()
    matrix, labels, groups, records = [], [], [], []
    cache_hits = 0
    cache = output / "feature_cache.json"
    cached = json.loads(cache.read_text()) if cache.exists() else {}
    if cached.get("extractor_version") != version_string:
        cached = {"extractor_version": version_string, "files": {}}
    started = time.perf_counter()
    for index, file in enumerate(files):
        label, actor = parse_name(file)
        raw = file.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        prior = cached["files"].get(digest)
        if prior:
            quality, features = prior["quality"], prior["features"]
            cache_hits += 1
        else:
            quality, features = extract_features(raw)
            cached["files"][digest] = {"quality": quality, "features": features}
        records.append({"filename": file.name, "actor": actor, "label": label, "audio_sha256": digest, "split": "train" if actor in TRAIN_ACTORS else "test", "quality": quality})
        if features is not None:
            matrix.append([features[n] for n in names])
            labels.append(label)
            groups.append(actor)
        if (index + 1) % 100 == 0:
            print(f"Features {index + 1}/{len(files)}", flush=True)
            cache.write_text(json.dumps(cached), encoding="utf-8")
    cache.write_text(json.dumps(cached), encoding="utf-8")
    x, y, g = np.asarray(matrix), np.asarray(labels), np.asarray(groups)
    if len(x) < 1296:
        raise ValueError("More than 10% of public files failed quality checks; inspect before reporting results.")
    train_idx, test_idx = np.flatnonzero(g <= 18), np.flatnonzero(g >= 19)
    assert not set(g[train_idx]) & set(g[test_idx])
    folds = list(StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42).split(x[train_idx], y[train_idx], g[train_idx]))
    fold_manifest, comparisons = [], {}
    for fold, (tr, va) in enumerate(folds):
        assert not set(g[train_idx][tr]) & set(g[train_idx][va])
        fold_manifest.append({"fold": fold, "train_actors": sorted(set(g[train_idx][tr].tolist())), "validation_actors": sorted(set(g[train_idx][va].tolist()))})
    all_models = candidates()
    for name, prototype in all_models.items():
        scores = []
        for tr, va in folds:
            estimator = clone(prototype).fit(x[train_idx][tr], y[train_idx][tr])
            predicted = estimator.predict(x[train_idx][va])
            scores.append(float(f1_score(y[train_idx][va], predicted, labels=LABELS, average="macro", zero_division=0)))
        comparisons[name] = {"cv_macro_f1_mean": float(np.mean(scores)), "cv_macro_f1_std": float(np.std(scores)), "cv_fold_macro_f1": scores}
        print(f"{name}: speaker-group CV macro F1={np.mean(scores):.4f}", flush=True)
    eligible = [name for name in comparisons if not name.startswith("dummy")]
    selected = max(eligible, key=lambda n: comparisons[n]["cv_macro_f1_mean"])
    # Selection is frozen BEFORE computing ANY held-out test metric.
    fitted = {}
    predictions = []
    for name, prototype in all_models.items():
        model = clone(prototype).fit(x[train_idx], y[train_idx])
        pred = model.predict(x[test_idx])
        comparisons[name]["heldout_test"] = metrics(y[test_idx], pred)
        comparisons[name]["heldout_test"]["classification_scope"] = "quality_accepted_recordings_only"
        comparisons[name]["heldout_test"]["accuracy_counting_abstentions_as_incorrect"] = float(np.sum(y[test_idx] == pred) / 360)
        fitted[name] = model
        if name == selected:
            accepted_test_records = [r for r in records if r["split"] == "test" and r["quality"]["status"] == "accepted"]
            predictions = [{"filename": r["filename"], "actor": r["actor"], "true_label": r["label"], "predicted_label": str(p)} for r, p in zip(accepted_test_records, pred)]
    model_path = output / "model.joblib"
    joblib.dump(fitted[selected], model_path, compress=3)
    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    manifest_sha = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    report = {"dataset": "RAVDESS speech", "label_order": LABELS, "source_files": len(files), "accepted_files": len(x), "rejected_files": len(files) - len(x),
              "feature_count": len(names), "train_samples": len(train_idx), "test_samples": len(test_idx), "train_actors": TRAIN_ACTORS, "test_actors": TEST_ACTORS,
              "cv_folds": fold_manifest, "selection_rule": "highest mean train-only speaker-group CV macro F1; heldout test never selects model", "selected_model": selected,
              "comparisons": comparisons, "test_predictions": predictions, "manifest_sha256": manifest_sha,
              "training_seconds": time.perf_counter() - started, "random_seed": 42, "no_synthetic_training_data": True, "no_test_retraining": True}
    report["quality_coverage"] = {
        split: {"total": len(rows), "accepted": sum(r["quality"]["status"] == "accepted" for r in rows),
                "rejected": sum(r["quality"]["status"] != "accepted" for r in rows),
                "accepted_fraction": sum(r["quality"]["status"] == "accepted" for r in rows) / len(rows),
                "rejected_by_label": {label: sum(r["label"] == label and r["quality"]["status"] != "accepted" for r in rows) for label in LABELS}}
        for split, rows in (("all", records), ("train", [r for r in records if r["split"] == "train"]), ("test", [r for r in records if r["split"] == "test"]))}
    report["feature_extraction_cache_reused"] = cache_hits > 0
    report["feature_extraction_cache_hits"] = cache_hits
    card = {"model_id": "c2-ravdess-egemaps-" + model_sha[:12], "created_at": datetime.now(timezone.utc).isoformat(),
            "selected_model": selected, "feature_schema_version": FEATURE_SCHEMA, "extractor_version": version_string,
            "feature_names": names, "labels": fitted[selected].classes_.tolist(), "model_sha256": model_sha,
            "training_data_source": "public_dataset", "dataset": "RAVDESS audio speech", "dataset_url": URL,
            "dataset_license": "CC-BY-NC-SA-4.0", "citation": CITATION, "train_actors": TRAIN_ACTORS, "test_actors": TEST_ACTORS,
            "evaluation_scope": "heldout_actors_within_RAVDESS_acted_English_speech_only", "clinical_validation": False,
            "test_metrics": comparisons[selected]["heldout_test"], "selection_rule": report["selection_rule"],
            "quality_coverage": report["quality_coverage"],
            "dependencies": {name: version(name) for name in ("scikit-learn", "numpy", "opensmile", "scipy", "soundfile", "joblib")}, "python": platform.python_version(),
            "limitations": ["Acted speech; two statements; 24 North American English-speaking actors.", "No validation on natural Sri Lankan student speech, Sinhala or Tamil.", "Classifier scores are uncalibrated decision scores, not wellbeing or diagnostic probabilities.", "No transcript, therapy, LLM, stress or burnout model is used."]}
    for filename, obj in (("model_card.json", card), ("evaluation.json", report), ("dataset_manifest.json", records)):
        (output / filename).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Selected {selected}. Held-out macro F1={card["test_metrics"]["macro_f1"]:.4f}; accuracy={card["test_metrics"]["accuracy"]:.4f}", flush=True)
    return card


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data/public/ravdess"))
    parser.add_argument("--output", type=Path, default=Path("models/voice"))
    args = parser.parse_args()
    train(args.dataset, args.output)
