"""Exploratory exhaustion-proxy training; synthetic metrics are not validation."""
import argparse
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.risk.features import BEHAVIOR_FEATURES, FEATURE_NAMES, FEATURE_SCHEMA, parse_time, snapshot, vector
from app.risk.schemas import DailyInput, STUDY_TIMEZONE, WeeklyInput
from training.generate_risk_data import generate

TARGET = "next_weekly_exhaustion_ge4_within_next7days"


class PersistenceBaseline(ClassifierMixin, BaseEstimator):
    def fit(self, x, y):
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = x.shape[1]
        self.prior_ = float(np.mean(y))
        return self

    def predict_proba(self, x):
        values = x[:, FEATURE_NAMES.index("latest_weekly_exhaustion")]
        positive = np.where(np.isnan(values), self.prior_, (values >= 4).astype(float))
        return np.column_stack([1 - positive, positive])

    def predict(self, x):
        return (self.predict_proba(x)[:, 1] >= .5).astype(int)


def pipeline(classifier, features=FEATURE_NAMES, scaled=False):
    select = ColumnTransformer([("selected", "passthrough", [FEATURE_NAMES.index(f) for f in features])], remainder="drop")
    steps = [select, SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)]
    if scaled:
        steps.append(StandardScaler())
    return make_pipeline(*steps, classifier)


def candidates():
    return {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "weekly_persistence": PersistenceBaseline(),
        "behavior_only_logistic": pipeline(LogisticRegression(C=1, class_weight="balanced", max_iter=3000, random_state=73), BEHAVIOR_FEATURES, True),
        "combined_logistic": pipeline(LogisticRegression(C=1, class_weight="balanced", max_iter=3000, random_state=73), scaled=True),
        "combined_random_forest": pipeline(RandomForestClassifier(n_estimators=120, max_depth=5, min_samples_leaf=12, class_weight="balanced", random_state=73, n_jobs=1)),
        "combined_gradient_boosting": pipeline(HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=9, learning_rate=.06, l2_regularization=2, class_weight="balanced", random_state=73)),
    }


def validate_dataset(dataset):
    source = dataset["data_source"]
    if source not in {"synthetic_demo", "local_research"} or dataset["study_timezone"] != STUDY_TIMEZONE:
        raise ValueError("Dataset must declare synthetic_demo/local_research and the configured study timezone")
    if len({p["participant_id"] for p in dataset["participants"]}) != len(dataset["participants"]):
        raise ValueError("Participant IDs must be unique")
    for person in dataset["participants"]:
        if person["data_source"] != source:
            raise ValueError("Participant source differs from the dataset source")
        for kind, schema in (("daily", DailyInput), ("weekly", WeeklyInput)):
            if len({r["observed_on"] for r in person[kind]}) != len(person[kind]):
                raise ValueError("Duplicate participant observation dates")
            for row in person[kind]:
                schema.model_validate({k: v for k, v in row.items() if k in schema.model_fields})
                if row["participant_id"] != person["participant_id"] or row["data_source"] != source or not row["consent"]:
                    raise ValueError("Mixed data sources/participant identifiers or absent consent")
                if parse_time(row["ingested_at"]) < parse_time(row["reported_at"]):
                    raise ValueError("Server availability cannot precede reporting")


def make_samples(dataset):
    samples = []
    rejected = 0
    for person in dataset["participants"]:
        for outcome in sorted(person["weekly"], key=lambda r: r["observed_on"]):
            target_day = date.fromisoformat(outcome["observed_on"])
            issue = target_day - timedelta(days=7)
            upcoming = [r for r in person["weekly"] if issue < date.fromisoformat(r["observed_on"]) <= target_day]
            if min(upcoming, key=lambda r: r["observed_on"])["record_id"] != outcome["record_id"]:
                # If assessments were more frequent than weekly, use only the
                # first future assessment in the forecast window as its target.
                rejected += 1
                continue
            as_of = datetime.combine(issue, time(23, 59), ZoneInfo(STUDY_TIMEZONE)).astimezone(timezone.utc)
            snap = snapshot(person["daily"], person["weekly"], as_of)
            if snap["status"] != "sufficient_history":
                rejected += 1
                continue
            assert outcome["record_id"] not in snap["input_record_ids"]["weekly"]
            samples.append({"participant_id": person["participant_id"], "as_of": snap["as_of"], "issue_date": issue.isoformat(),
                            "target_date": target_day.isoformat(), "label_available_at": max(parse_time(outcome["ingested_at"]), parse_time(outcome["reported_at"])).isoformat(),
                            "label": int(outcome["exhaustion"] >= 4), "features": snap["features"], "input_record_ids": snap["input_record_ids"]})
    return samples, rejected


def metrics(y, probability):
    predicted = (probability >= .5).astype(int)
    return {"sample_count": len(y), "positive_count": int(sum(y)), "positive_fraction": float(np.mean(y)),
            "roc_auc": float(roc_auc_score(y, probability)) if len(np.unique(y)) == 2 else None,
            "average_precision": float(average_precision_score(y, probability)) if sum(y) else None,
            "brier_score": float(brier_score_loss(y, probability)), "accuracy": float(accuracy_score(y, predicted)),
            "balanced_accuracy": float(balanced_accuracy_score(y, predicted)), "f1": float(f1_score(y, predicted, zero_division=0)),
            "confusion_matrix_0_1": confusion_matrix(y, predicted, labels=[0, 1]).tolist(), "threshold": .5}


def train(path, output, allow_local=False):
    raw = path.read_bytes()
    dataset = json.loads(raw)
    if dataset["data_source"] == "local_research" and not allow_local:
        raise ValueError("Local-data fitting requires --allow-local-research and genuine approved observations/labels")
    validate_dataset(dataset)
    people = sorted(p["participant_id"] for p in dataset["participants"])
    if len(people) < 30:
        raise ValueError("This comparison protocol requires at least 30 participants; smaller pilots need a separate evaluation design")
    samples, rejected = make_samples(dataset)
    if not samples:
        raise ValueError("No eligible longitudinal training windows")
    dates = [date.fromisoformat(r["observed_on"]) for p in dataset["participants"] for r in p["daily"]]
    first, last = min(dates), max(dates)
    duration = (last - first).days + 1
    local_pilot = dataset["data_source"] == "local_research"
    minimum_days = 42 if local_pilot else 84
    if duration < minimum_days:
        raise ValueError(f"This fitting protocol requires at least {minimum_days} observed study days. A shorter pilot should report feasibility/descriptives; do not fabricate additional days.")
    shuffled = np.random.default_rng(73).permutation(people).tolist()
    test_people = sorted(shuffled[:max(6, len(people) // 5)])
    train_people = sorted(set(people) - set(test_people))
    cutoff = first + timedelta(days=int(duration * (.52 if local_pilot else .7)))
    end_cutoff = datetime.combine(cutoff, time.max, ZoneInfo(STUDY_TIMEZONE)).astimezone(timezone.utc)
    train_idx = [i for i, s in enumerate(samples) if s["participant_id"] in train_people and parse_time(s["label_available_at"]) <= end_cutoff]
    test_idx = [i for i, s in enumerate(samples) if s["participant_id"] in test_people and date.fromisoformat(s["issue_date"]) > cutoff]
    x = np.array([vector(s["features"]) for s in samples])
    y = np.array([s["label"] for s in samples])
    if len(train_idx) < (20 if local_pilot else 60) or len(test_idx) < (10 if local_pilot else 20) or len(np.unique(y[train_idx])) < 2 or len(np.unique(y[test_idx])) < 2:
        raise ValueError("Insufficient eligible person/time-separated examples or outcome classes")
    folds, fold_report = [], []
    validation_groups = np.array_split(np.array(train_people), 3)
    for index, group in ([] if local_pilot else enumerate(validation_groups)):
        fold_cutoff = first + timedelta(days=28 + index * 7)
        fold_time = datetime.combine(fold_cutoff, time.max, ZoneInfo(STUDY_TIMEZONE)).astimezone(timezone.utc)
        validation_people = set(group.tolist())
        tr = [i for i in train_idx if samples[i]["participant_id"] not in validation_people and parse_time(samples[i]["label_available_at"]) <= fold_time]
        va = [i for i in train_idx if samples[i]["participant_id"] in validation_people and fold_cutoff < date.fromisoformat(samples[i]["issue_date"]) <= fold_cutoff + timedelta(days=14)]
        if len(tr) < 20 or len(va) < 10 or len(np.unique(y[tr])) < 2 or len(np.unique(y[va])) < 2:
            raise ValueError("Insufficient class diversity in a purged CV fold; do not fill missing labels synthetically")
        folds.append((tr, va))
        fold_report.append({"fold": index, "training_labels_available_by": fold_time.isoformat(),
                            "train_participants": sorted({samples[i]["participant_id"] for i in tr}), "validation_participants": sorted({samples[i]["participant_id"] for i in va}),
                            "train_count": len(tr), "validation_count": len(va),
                            "max_train_label_time": max(samples[i]["label_available_at"] for i in tr), "min_validation_issue_date": min(samples[i]["issue_date"] for i in va)})
    comparison = {}
    prototypes = candidates()
    for name, prototype in prototypes.items():
        scores = []
        for tr, va in folds:
            fitted = clone(prototype).fit(x[tr], y[tr])
            scores.append(float(roc_auc_score(y[va], fitted.predict_proba(x[va])[:, 1])))
        comparison[name] = {"cv_roc_auc_mean": float(np.mean(scores)) if scores else None, "cv_roc_auc_by_fold": scores}
        print(f"{name}: purged participant/time CV AUC={np.mean(scores):.4f}" if scores else f"{name}: local pilot; no hyperparameter-selection CV", flush=True)
    eligible_models = [n for n in prototypes if n not in {"dummy_prior", "weekly_persistence"}]
    selected = "combined_logistic" if local_pilot else max(eligible_models, key=lambda n: comparison[n]["cv_roc_auc_mean"])
    fitted_models = {}
    for name, prototype in prototypes.items():
        fitted = clone(prototype).fit(x[train_idx], y[train_idx])
        comparison[name]["heldout_test"] = metrics(y[test_idx], fitted.predict_proba(x[test_idx])[:, 1])
        fitted_models[name] = fitted
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(fitted_models[selected], output / "model.joblib", compress=3)
    model_hash = hashlib.sha256((output / "model.joblib").read_bytes()).hexdigest()
    report = {"data_source": dataset["data_source"], "synthetic_only": dataset["data_source"] == "synthetic_demo", "target": TARGET,
              "source_participants": len(people), "eligible_windows": len(samples), "insufficient_history_windows": rejected,
              "train_samples": len(train_idx), "test_samples": len(test_idx), "train_participants": train_people, "test_participants": test_people,
              "global_training_label_cutoff": end_cutoff.isoformat(), "cv_folds": fold_report,
              "selection_rule": "prespecified combined logistic C=1 for small local pilot; no test-based selection or CV claim" if local_pilot else "highest purged participant/time CV ROC AUC among learned models; heldout metrics never select model",
              "selected_model": selected, "comparisons": comparison, "feature_names": FEATURE_NAMES,
              "dataset_sha256": hashlib.sha256(raw).hexdigest(), "generator_version": dataset.get("generator_version"), "random_seed": 73,
              "warning": "Synthetic performance only tests this simulator; it cannot estimate real-student predictive performance." if dataset["data_source"] == "synthetic_demo" else "Exploratory local proxy; not a clinically validated burnout assessment."}
    probability = fitted_models[selected].predict_proba(x[test_idx])[:, 1]
    report["test_predictions"] = [{"participant_id": samples[i]["participant_id"], "as_of": samples[i]["as_of"], "target_date": samples[i]["target_date"], "label": int(y[i]), "model_probability": float(p)} for i, p in zip(test_idx, probability)]
    if dataset["data_source"] == "synthetic_demo":
        shifted = generate(participants=80, days=98, seed=947, shifted=True)
        shifted_samples, _ = make_samples(shifted)
        sx = np.array([vector(s["features"]) for s in shifted_samples])
        sy = np.array([s["label"] for s in shifted_samples])
        report["independent_shifted_simulation"] = {"seed": 947, "participants": 80, "metrics": metrics(sy, fitted_models[selected].predict_proba(sx)[:, 1]), "not_real_world_validation": True}
    card = {"model_id": "c3-exhaustion-proxy-" + model_hash[:12], "created_at": datetime.now(timezone.utc).isoformat(),
            "training_data_source": dataset["data_source"], "synthetic_only": report["synthetic_only"],
            "validation_status": "synthetic_only_not_empirically_validated" if report["synthetic_only"] else "exploratory_local_proxy_not_clinical",
            "feature_schema_version": FEATURE_SCHEMA, "feature_names": FEATURE_NAMES, "selected_model": selected, "model_sha256": model_hash,
            "target": TARGET, "lookback_complete_days": 14, "horizon_days": 7, "study_timezone": STUDY_TIMEZONE,
            "decision_threshold": .5, "threshold_status": "engineering_demo_setting_not_clinical_cutoff", "clinical_validation": False,
            "weekly_instrument": "exploratory-exhaustion-item-v1", "instrument_validated": False,
            "test_metrics": comparison[selected]["heldout_test"], "dataset_sha256": report["dataset_sha256"],
            "dependencies": {n: version(n) for n in ("numpy", "scikit-learn", "joblib")},
            "modalities_used": ["daily_behavior"] if selected == "behavior_only_logistic" else ["daily_behavior", "daily_self_report", "prior_weekly_self_report"], "facial_or_voice_scores_used_as_risk_predictors": False,
            "limitations": ["Exhaustion >=4 is an exploratory single-item proxy, not a validated burnout diagnosis.", "Synthetic metrics do not validate local student accuracy or probability calibration.", "Missing daily values are imputed using training-only medians; no zero-filling of missing days.", "Raw facial deviation/acted voice emotion are not converted into clinical risk."]}
    assignments = [{"participant_id": s["participant_id"], "as_of": s["as_of"], "label_available_at": s["label_available_at"], "target_date": s["target_date"], "split": "train" if i in train_idx else "test" if i in test_idx else "purged_or_unused"} for i, s in enumerate(samples)]
    for filename, value in (("model_card.json", card), ("evaluation.json", report), ("split_manifest.json", assignments)):
        (output / filename).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Selected {selected}; data_source={dataset["data_source"]}; test AUC={card["test_metrics"]["roc_auc"]:.4f}. This is not burnout validation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("data/synthetic/risk_dataset.json"))
    parser.add_argument("--output", type=Path, default=Path("models/risk"))
    parser.add_argument("--allow-local-research", action="store_true")
    args = parser.parse_args()
    train(args.dataset, args.output, args.allow_local_research)
