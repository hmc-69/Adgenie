"""Strict loader and inference wrapper for AdGenie's local audience experiment.

The artifact is a trusted, synthetic-only experiment output. This module loads
only its fixed group-aware model path and never selects a Gemini/mock fallback.
"""

from __future__ import annotations

import json
import hashlib
import math
import platform
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = (
    PROJECT_ROOT
    / "backend"
    / "datasets"
    / "audience_analysis"
    / "experimental_output"
    / "synthetic-run-20261020T145421Z-seed-42"
)
MODEL_FILENAME = "tfidf_logistic_regression.joblib"
MODEL_SHA256 = "7ca946ff0d54c8de0361f6c447e5110e425b14491c46afd9d21496796880e972"
MODEL_IDENTIFIER = "audience-tfidf-logistic-regression@synthetic-run-20261020T145421Z-seed-42"
FEATURE_COLUMNS = ("product_name", "description", "platform", "objective", "tone", "keywords")
ALLOWED_LABELS = frozenset(
    {
        "convenience_seekers",
        "value_seekers",
        "quality_seekers",
        "style_seekers",
        "learning_seekers",
        "business_utility_seekers",
        "hobby_interest_seekers",
        "gift_shoppers",
        "general_interest",
    }
)


class AudienceClassifierError(RuntimeError):
    """Raised when the fixed experimental classifier cannot safely predict."""


def _read_manifest(artifact_root: Path) -> dict[str, Any]:
    manifest_path = artifact_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AudienceClassifierError("Audience classifier manifest is missing or invalid.") from exc
    if not isinstance(manifest, dict):
        raise AudienceClassifierError("Audience classifier manifest has an invalid structure.")

    required = {
        "status": "synthetic_experiment_only",
        "target_column": "dominant_archetype",
        "feature_columns": list(FEATURE_COLUMNS),
        "seed": 42,
        "scikit_learn_version": "1.8.0",
    }
    if any(manifest.get(key) != value for key, value in required.items()):
        raise AudienceClassifierError("Audience classifier manifest is incompatible with the expected model.")
    mapping = manifest.get("class_mapping")
    if not isinstance(mapping, dict) or set(mapping) != ALLOWED_LABELS or set(mapping.values()) != set(range(9)):
        raise AudienceClassifierError("Audience classifier manifest has an invalid class mapping.")
    primary = manifest.get("evaluation_splits", {}).get("group_aware", {})
    if (
        not isinstance(primary, dict)
        or primary.get("group_overlap_count") != 0
        or "group-aware" not in str(primary.get("split_method", ""))
    ):
        raise AudienceClassifierError("Audience classifier manifest does not identify the expected group-aware model.")
    try:
        metrics = json.loads((artifact_root / "metrics.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AudienceClassifierError("Audience classifier metrics are missing or invalid.") from exc
    metric_primary = metrics.get("evaluations", {}).get("group_aware", {}) if isinstance(metrics, dict) else {}
    if (
        not isinstance(metrics, dict)
        or metrics.get("status") != "synthetic_experiment_only"
        or metrics.get("primary_evaluation") != "group_aware"
        or not isinstance(metric_primary, dict)
        or metric_primary.get("group_overlap_count") != 0
        or metric_primary.get("model_artifact") != MODEL_FILENAME
    ):
        raise AudienceClassifierError("Audience classifier metrics do not identify the expected group-aware model.")
    if not str(manifest.get("artifact_trust", "")).startswith("Trusted local output created by this script"):
        raise AudienceClassifierError("Audience classifier artifact provenance is not recognized.")
    if PureWindowsPath(str(manifest.get("dataset_path", ""))).name != "synthetic_audience_drafts_v3.csv":
        raise AudienceClassifierError("Audience classifier manifest references an unexpected dataset.")
    dataset_path = artifact_root.parents[1] / "synthetic_audience_drafts_v3.csv"
    try:
        dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AudienceClassifierError("Audience classifier source dataset is missing.") from exc
    if dataset_hash != manifest.get("dataset_sha256"):
        raise AudienceClassifierError("Audience classifier source dataset hash does not match its manifest.")
    return manifest


def _check_runtime(manifest: Mapping[str, Any]) -> None:
    expected = manifest.get("dependency_versions")
    if not isinstance(expected, dict):
        raise AudienceClassifierError("Audience classifier manifest has no dependency versions.")
    try:
        sklearn_version = version("scikit-learn")
        joblib_version = version("joblib")
    except PackageNotFoundError as exc:
        raise AudienceClassifierError(
            "Audience classifier dependencies are not installed. Install the pinned experimental requirements."
        ) from exc
    expected_python = str(manifest.get("python_version", "")).split(".")[:2]
    if expected_python != platform.python_version().split(".")[:2]:
        raise AudienceClassifierError("Python runtime does not match the audience classifier artifact environment.")
    if sklearn_version != expected.get("scikit-learn") or joblib_version != expected.get("joblib"):
        raise AudienceClassifierError("Installed scikit-learn/joblib versions do not match the saved artifact.")


@lru_cache(maxsize=1)
def _load_expected_model():
    manifest = _read_manifest(ARTIFACT_ROOT)
    _check_runtime(manifest)
    model_path = (ARTIFACT_ROOT / MODEL_FILENAME).resolve()
    if model_path.parent != ARTIFACT_ROOT.resolve() or not model_path.is_file():
        raise AudienceClassifierError("Expected audience classifier model artifact is missing or invalid.")
    try:
        model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AudienceClassifierError("Expected audience classifier model artifact is missing or invalid.") from exc
    if model_hash != MODEL_SHA256:
        raise AudienceClassifierError("Audience classifier model artifact hash does not match the trusted local model.")
    try:
        import joblib

        model = joblib.load(model_path)
    except AudienceClassifierError:
        raise
    except Exception as exc:
        raise AudienceClassifierError("Expected audience classifier model artifact could not be loaded.") from exc

    named_steps = getattr(model, "named_steps", None)
    classifier = named_steps.get("classifier") if isinstance(named_steps, Mapping) else None
    classes = getattr(classifier, "classes_", None)
    if (
        not isinstance(named_steps, Mapping)
        or set(named_steps) != {"tfidf", "classifier"}
        or not callable(getattr(model, "predict", None))
        or classes is None
        or set(classes) != ALLOWED_LABELS
        or not callable(getattr(model, "predict_proba", None))
    ):
        raise AudienceClassifierError("Loaded audience classifier does not match the expected TF-IDF pipeline.")
    return model


def predict_audience_archetype(campaign: Mapping[str, Any]) -> dict[str, Any]:
    """Predict an archetype from the six approved campaign brief text fields."""
    if not isinstance(campaign, Mapping):
        raise AudienceClassifierError("Campaign context must be a mapping of campaign fields.")
    values: list[str] = []
    for field in FEATURE_COLUMNS:
        value = campaign.get(field)
        if value is None:
            values.append("")
        elif isinstance(value, str):
            values.append(value.strip())
        else:
            raise AudienceClassifierError(f"Campaign field {field!r} must be text or empty.")
    text = " ".join(values).strip()
    if not text:
        raise AudienceClassifierError("At least one campaign brief text field is required for prediction.")

    model = _load_expected_model()
    try:
        predicted = str(model.predict([text])[0])
        class_labels = [str(label) for label in model.named_steps["classifier"].classes_]
        scores = [float(value) for value in model.predict_proba([text])[0]]
    except Exception as exc:
        raise AudienceClassifierError("Audience classifier prediction failed.") from exc
    if predicted not in ALLOWED_LABELS or len(scores) != len(class_labels) or not all(math.isfinite(v) for v in scores):
        raise AudienceClassifierError("Audience classifier returned an invalid prediction.")
    return {
        "predicted_archetype": predicted,
        "model_identifier": MODEL_IDENTIFIER,
        "model_status": "synthetic_experiment_only",
        "class_scores": dict(zip(class_labels, scores)),
        "score_type": "uncalibrated_model_scores; not verified probabilities or audience facts",
    }
