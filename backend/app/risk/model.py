import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np

from app.risk.features import FEATURE_NAMES, FEATURE_SCHEMA, vector


class RiskModel:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.pipeline = None
        self.card = None
        self.reason = "model_artifacts_missing"

    def load(self):
        self.pipeline, self.card = None, None
        try:
            card = json.loads((self.directory / "model_card.json").read_text())
            path = self.directory / "model.joblib"
            if hashlib.sha256(path.read_bytes()).hexdigest() != card["model_sha256"]:
                raise ValueError("Checksum mismatch")
            if card["feature_schema_version"] != FEATURE_SCHEMA or card["feature_names"] != FEATURE_NAMES:
                raise ValueError("Feature mismatch")
            if card["training_data_source"] not in {"synthetic_demo", "local_research"}:
                raise ValueError("Unsupported model provenance")
            for dependency in ("scikit-learn", "numpy", "joblib"):
                if version(dependency) != card["dependencies"][dependency]:
                    raise ValueError("Dependency mismatch")
            pipeline = joblib.load(path)  # Trusted project-generated local artifacts only.
            if pipeline.classes_.tolist() != [0, 1] or pipeline.n_features_in_ != len(FEATURE_NAMES):
                raise ValueError("Classifier dimensions/classes mismatch")
            self.card, self.pipeline, self.reason = card, pipeline, None
        except FileNotFoundError:
            self.reason = "model_artifacts_missing"
        except Exception:
            self.reason = "model_artifact_or_dependency_incompatible"
        return self

    def status(self):
        return {"status": "ready" if self.pipeline is not None else "unavailable", "reason": self.reason,
                "model_id": self.card["model_id"] if self.card else None,
                "training_data_source": self.card["training_data_source"] if self.card else None,
                "validation_status": self.card["validation_status"] if self.card else "not_validated",
                "trained_burnout_model": False, "clinical_validation": False}

    def predict(self, features):
        probability = float(self.pipeline.predict_proba(np.array([vector(features)]))[:, 1][0])
        return {"model_probability": probability, "probability_scope": "uncalibrated_simulation_probability" if self.card["synthetic_only"] else "uncalibrated_exploratory_exhaustion_proxy",
                "proxy_band": "higher_proxy_score" if probability >= self.card["decision_threshold"] else "lower_proxy_score",
                "decision_threshold": self.card["decision_threshold"], "clinical_risk_probability": None,
                "model_id": self.card["model_id"], "target": self.card["target"]}
