"""Strict loader and inference wrapper for the local synthetic-rate experiment."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.schemas.campaign_prediction import (
    CampaignPerformancePredictionResponse,
    CampaignPredictionFeatures,
    CampaignPredictionValues,
    TargetEvaluation,
)
from app.services.campaign_service import get_owned_campaign


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_ROOT = BACKEND_ROOT / "models" / "campaign_performance_prediction"
FEATURE_SCHEMA = [
    "product_name", "description", "target_audience", "platform", "objective", "tone", "budget", "keywords"
]
TARGET_SCHEMA = ["ctr_percent", "conversion_rate_percent"]
EXPECTED_ARTIFACT = "campaign_performance_pipelines.joblib"
LIMITATIONS = [
    "Trained and evaluated on synthetic data only.",
    "Synthetic test metrics do not demonstrate real-world advertising accuracy.",
    "Predictions are experimental estimates, not observed campaign performance or a guarantee.",
]


class CampaignPredictionArtifactError(Exception):
    """The configured local synthetic prediction artifact is absent or invalid."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CampaignPredictionArtifactError("Campaign prediction metadata is missing or invalid.") from exc
    if not isinstance(data, dict):
        raise CampaignPredictionArtifactError("Campaign prediction metadata is invalid.")
    return data


def _model_root() -> Path:
    configured = os.getenv("CAMPAIGN_PERFORMANCE_MODEL_DIR")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_MODEL_ROOT.resolve()


def _verify_runtime(manifest: dict[str, Any]) -> None:
    python_parts = str(manifest.get("python_version", "")).split(".")[:2]
    if python_parts != platform.python_version().split(".")[:2]:
        raise CampaignPredictionArtifactError("The active model was trained with an incompatible Python version.")
    expected_dependencies = manifest.get("dependency_versions", {})
    try:
        required_packages = ("scikit-learn", "joblib", "numpy", "scipy")
        installed = {package: version(package) for package in required_packages}
    except PackageNotFoundError as exc:
        raise CampaignPredictionArtifactError(
            "Campaign prediction dependencies are not installed. Use the pinned experimental requirements."
        ) from exc
    if any(installed[name] != expected_dependencies.get(name) for name in installed):
        raise CampaignPredictionArtifactError("Installed scikit-learn/joblib versions do not match the active model.")


@lru_cache(maxsize=4)
def _load_model_bundle(model_root: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = Path(model_root).resolve()
    active = _read_json(root / "active.json")
    model_version = active.get("model_version")
    if not isinstance(model_version, str) or not model_version.replace("-", "").replace("_", "").isalnum():
        raise CampaignPredictionArtifactError("The active campaign prediction model version is invalid.")
    version_dir = (root / model_version).resolve()
    if version_dir.parent != root or not version_dir.is_dir():
        raise CampaignPredictionArtifactError("The active campaign prediction model directory is missing or invalid.")
    manifest = _read_json(version_dir / "manifest.json")
    if (
        manifest.get("artifact_status") != "synthetic_experiment_only"
        or manifest.get("synthetic_data") is not True
        or manifest.get("model_version") != model_version
        or manifest.get("feature_schema") != FEATURE_SCHEMA
        or manifest.get("targets") != TARGET_SCHEMA
        or not str(manifest.get("artifact_trust", "")).startswith("Trusted local output created by train_model.py")
    ):
        raise CampaignPredictionArtifactError("The active model manifest does not match the expected synthetic experiment.")
    _verify_runtime(manifest)
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != {
        EXPECTED_ARTIFACT, "metrics.json", "dataset_metadata.json"
    }:
        raise CampaignPredictionArtifactError("The active model manifest has an invalid artifact file list.")
    resolved_files = {}
    for name, expected_hash in files.items():
        path = (version_dir / name).resolve()
        if path.parent != version_dir or not path.is_file():
            raise CampaignPredictionArtifactError("A required campaign prediction artifact is missing or invalid.")
        if not isinstance(expected_hash, str) or _sha256(path) != expected_hash:
            raise CampaignPredictionArtifactError("A campaign prediction artifact checksum does not match its manifest.")
        resolved_files[name] = path

    metrics = _read_json(resolved_files["metrics.json"])
    dataset_metadata = _read_json(resolved_files["dataset_metadata.json"])
    if (
        metrics.get("status") != "synthetic_experiment_only"
        or metrics.get("dataset_type") != "synthetic"
        or metrics.get("dataset_sha256") != manifest.get("dataset_sha256")
        or metrics.get("feature_schema") != FEATURE_SCHEMA
        or dataset_metadata.get("dataset_sha256") != manifest.get("dataset_sha256")
        or dataset_metadata.get("synthetic_data") is not True
        or manifest.get("selected_models") != {
            target: metrics.get("evaluation", {}).get(target, {}).get("selected_model")
            for target in TARGET_SCHEMA
        }
    ):
        raise CampaignPredictionArtifactError("The campaign prediction evaluation metadata is inconsistent.")

    try:
        import joblib

        bundle = joblib.load(resolved_files[EXPECTED_ARTIFACT])
    except CampaignPredictionArtifactError:
        raise
    except Exception as exc:
        raise CampaignPredictionArtifactError("The trusted campaign prediction pipeline could not be loaded.") from exc
    if (
        not isinstance(bundle, dict)
        or bundle.get("version") != model_version
        or bundle.get("feature_schema") != FEATURE_SCHEMA
        or not isinstance(bundle.get("models"), dict)
        or set(bundle["models"]) != set(TARGET_SCHEMA)
        or any(not callable(getattr(bundle["models"][target], "predict", None)) for target in TARGET_SCHEMA)
    ):
        raise CampaignPredictionArtifactError("The loaded campaign prediction pipeline has an invalid schema.")
    return manifest, metrics, bundle


def load_model_bundle() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _load_model_bundle(str(_model_root()))


def _evaluation_entry(metrics: dict[str, Any], target: str) -> TargetEvaluation:
    evaluation = metrics.get("evaluation", {}).get(target)
    if not isinstance(evaluation, dict):
        raise CampaignPredictionArtifactError("Saved campaign prediction evaluation results are missing.")
    selected = evaluation.get("test_metrics")
    baseline = evaluation.get("baseline_test_metrics")
    if not isinstance(selected, dict) or not isinstance(baseline, dict):
        raise CampaignPredictionArtifactError("Saved campaign prediction test metrics are invalid.")
    try:
        return TargetEvaluation(
            selected_model=evaluation["selected_model"],
            test_mae=selected["mae"],
            test_rmse=selected["rmse"],
            test_r2=selected["r2"],
            baseline_model=evaluation["baseline_model"],
            baseline_test_mae=baseline["mae"],
            baseline_test_rmse=baseline["rmse"],
            baseline_test_r2=baseline["r2"],
            meaningful_improvement_over_baseline=evaluation["meaningful_improvement_over_baseline"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CampaignPredictionArtifactError("Saved campaign prediction test metrics are invalid.") from exc


def _campaign_features(campaign: Campaign) -> CampaignPredictionFeatures:
    try:
        return CampaignPredictionFeatures.model_validate({
            "product_name": campaign.product_name,
            "description": campaign.description,
            "target_audience": campaign.target_audience,
            "platform": campaign.platform,
            "objective": campaign.objective,
            "tone": campaign.tone,
            "budget": campaign.budget,
            "keywords": campaign.keywords,
        })
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Campaign is missing valid pre-launch prediction fields.") from exc


def predict_campaign_performance(db: Session, campaign_id: int, user_id: int) -> dict[str, Any]:
    campaign = get_owned_campaign(db, campaign_id, user_id)
    features = _campaign_features(campaign)
    try:
        manifest, metrics, bundle = load_model_bundle()
    except CampaignPredictionArtifactError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    row = features.model_dump(mode="python")
    for field in ("platform", "objective", "tone"):
        row[field] = row[field].value
    row["budget"] = float(row["budget"]) if row["budget"] is not None else None
    try:
        import numpy as np

        frame = np.asarray([[
            (np.nan if field == "budget" and row[field] is None else row[field])
            for field in FEATURE_SCHEMA
        ]], dtype=object)
        raw_predictions = {
            target: float(bundle["models"][target].predict(frame)[0])
            for target in TARGET_SCHEMA
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Campaign performance prediction failed.") from exc
    if not all(math.isfinite(value) for value in raw_predictions.values()):
        raise HTTPException(status_code=500, detail="Campaign performance prediction returned a non-finite value.")
    bounded = {target: min(100.0, max(0.0, value)) for target, value in raw_predictions.items()}
    try:
        evaluation = {
            "dataset_type": metrics["dataset_type"],
            "ctr": _evaluation_entry(metrics, "ctr_percent"),
            "conversion_rate": _evaluation_entry(metrics, "conversion_rate_percent"),
        }
        return CampaignPerformancePredictionResponse(
            campaign_id=campaign_id,
            prediction_type="synthetic_experiment_only",
            model_version=manifest["model_version"],
            predictions=CampaignPredictionValues(
                ctr_percent=bounded["ctr_percent"],
                conversion_rate_percent=bounded["conversion_rate_percent"],
            ),
            units={"ctr_percent": "%", "conversion_rate_percent": "%"},
            evaluation=evaluation,
            output_bound_strategy=metrics["prediction_bounds"]["strategy"],
            limitations=LIMITATIONS,
        ).model_dump()
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Campaign prediction evaluation metadata is invalid.") from exc
