import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np

from app.voice.features import FEATURE_SCHEMA, extractor_version, feature_names


class VoiceModel:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.pipeline = None
        self.card = None
        self.reason = "model_artifacts_missing"

    def load(self):
        try:
            card = json.loads((self.directory / "model_card.json").read_text(encoding="utf-8"))
            model_path = self.directory / "model.joblib"
            if hashlib.sha256(model_path.read_bytes()).hexdigest() != card["model_sha256"]:
                raise ValueError("model_checksum_mismatch")
            if card["feature_schema_version"] != FEATURE_SCHEMA or card["feature_names"] != feature_names() or card["extractor_version"] != extractor_version():
                raise ValueError("extractor_schema_mismatch")
            for package in ("scikit-learn", "numpy", "joblib"):
                if version(package) != card["dependencies"][package]:
                    raise ValueError("model_dependency_version_mismatch")
            # Project-controlled local artifacts ONLY; never expose model upload.
            self.pipeline = joblib.load(model_path)
            if self.pipeline.classes_.tolist() != card["labels"] or self.pipeline.n_features_in_ != 88:
                raise ValueError("model_class_or_dimension_mismatch")
            self.card, self.reason = card, None
        except FileNotFoundError:
            self.reason = "model_artifacts_missing"
            self.pipeline = None
        except Exception:
            self.reason = "model_artifact_or_dependency_incompatible"
            self.pipeline = None
        return self

    def status(self):
        return {"status": "ready" if self.pipeline is not None else "unavailable", "reason": self.reason,
                "method": "eGeMAPSv02 + speaker-separated sklearn baseline", "model_id": self.card["model_id"] if self.card else None,
                "trained_wellbeing_model": False, "trained_emotion_style_model": self.pipeline is not None,
                "training_data_source": "public_dataset", "clinical_validation": False}

    def predict(self, features):
        if self.pipeline is None:
            raise RuntimeError("Voice model is unavailable")
        x = np.array([[features[n] for n in self.card["feature_names"]]], dtype=float)
        if not np.isfinite(x).all():
            raise ValueError("Nonfinite inference features")
        label = str(self.pipeline.predict(x)[0])
        scores = np.asarray(self.pipeline.decision_function(x))[0]
        return {"predicted_emotion_style": label,
                "decision_scores": {str(c): float(s) for c, s in zip(self.pipeline.classes_, scores)},
                "score_type": "uncalibrated_multiclass_decision_scores_not_probabilities",
                "probabilities": None, "model_id": self.card["model_id"], "baseline_model": self.card["selected_model"],
                "domain_status": "evaluated_on_heldout_RAVDESS_actors_only"}
