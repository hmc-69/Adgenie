"""Train and evaluate trusted local synthetic campaign-rate regressors."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

try:
    from .generate_dataset import DEFAULT_OUTPUT, FEATURES, TARGETS
except ImportError:  # Support running this file directly as a script.
    from generate_dataset import DEFAULT_OUTPUT, FEATURES, TARGETS


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_DATASET = DEFAULT_OUTPUT / "campaign_performance_synthetic.csv"
DEFAULT_OUTPUT_ROOT = BACKEND_ROOT / "models" / "campaign_performance_prediction"
TARGET_COLUMNS = tuple(TARGETS)
FORBIDDEN_FEATURES = {
    "impressions", "clicks", "conversions", "spend", "actual_spend", "revenue", "roi",
    "ctr_percent", "conversion_rate_percent", "campaign_id", "user_id", "id", "scenario_group",
}
CATEGORICAL_FEATURES = [3, 4, 5]
TEXT_FEATURES = [0, 1, 2, 7]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_by_group(groups: np.ndarray, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if groups.ndim != 1 or len(groups) == 0:
        raise ValueError("A non-empty group vector is required for leakage-safe splitting.")
    split_features = np.zeros((len(groups), 1))
    group_split = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed)
    train_validation_idx, test_idx = next(
        group_split.split(split_features, groups=groups)
    )
    validation_split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed + 1)
    train_relative, validation_relative = next(
        validation_split.split(split_features[train_validation_idx], groups=groups[train_validation_idx])
    )
    train_idx = train_validation_idx[train_relative]
    validation_idx = train_validation_idx[validation_relative]
    return train_idx, validation_idx, test_idx


def _text_pipeline() -> Pipeline:
    return Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="")),
        ("flatten", FunctionTransformer(np.ravel)),
        ("tfidf", TfidfVectorizer(max_features=350, ngram_range=(1, 2), min_df=2)),
    ])


def make_preprocessor() -> ColumnTransformer:
    transformers = [(f"text_{field}", _text_pipeline(), [field]) for field in TEXT_FEATURES]
    transformers.extend([
        ("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("budget", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), [6]),
    ])
    return ColumnTransformer(transformers=transformers, remainder="drop")


def make_pipeline(estimator) -> Pipeline:
    return Pipeline([("preprocess", make_preprocessor()), ("regressor", estimator)])


def candidate_estimators(seed: int) -> dict:
    return {
        "dummy_mean": DummyRegressor(strategy="mean"),
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(
            n_estimators=120,
            min_samples_leaf=4,
            max_features=0.9,
            random_state=seed,
            n_jobs=1,
        ),
    }


def calculate_metrics(actual, predicted) -> dict[str, float]:
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    if not np.isfinite(predicted_values).all():
        raise ValueError("Predictions must be finite before metric calculation.")
    return {
        "mae": float(mean_absolute_error(actual_values, predicted_values)),
        "rmse": float(np.sqrt(mean_squared_error(actual_values, predicted_values))),
        "r2": float(r2_score(actual_values, predicted_values)),
    }


def train_experiment(
    dataset_path: Path = DEFAULT_DATASET,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    version_name: str = "campaign-performance-v1",
    seed: int = 42,
) -> dict:
    if set(FEATURES) & FORBIDDEN_FEATURES:
        raise ValueError("Feature schema includes an outcome or identifier that can leak targets.")
    if not version_name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Version name may contain only letters, numbers, hyphens, and underscores.")
    dataset_path = dataset_path.resolve()
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Synthetic dataset not found: {dataset_path}")
    with dataset_path.open("r", encoding="utf-8", newline="") as dataset_file:
        reader = csv.DictReader(dataset_file)
        dataset_columns = set(reader.fieldnames or ())
        rows = list(reader)
    required = set(FEATURES) | set(TARGET_COLUMNS) | {"scenario_group"}
    if not required.issubset(dataset_columns):
        raise ValueError(f"Dataset is missing required columns: {sorted(required - dataset_columns)}")
    if len(rows) < 100:
        raise ValueError("At least 100 synthetic observations are required for a useful experiment.")
    metadata_path = dataset_path.with_name("dataset_metadata.json")
    if not metadata_path.is_file():
        raise ValueError("Dataset metadata is required to train this experiment.")
    dataset_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not dataset_metadata.get("synthetic_data") or _sha256(dataset_path) != dataset_metadata.get("dataset_sha256"):
        raise ValueError("Dataset is not marked synthetic or its checksum does not match metadata.")
    if dataset_metadata.get("row_count") != len(rows):
        raise ValueError("Dataset row count does not match its metadata.")
    groups = np.asarray([row["scenario_group"] for row in rows], dtype=str)
    X = np.asarray([
        [
            row["product_name"], row["description"], row["target_audience"], row["platform"],
            row["objective"], row["tone"], float(row["budget"]) if row["budget"] else np.nan,
            row["keywords"],
        ]
        for row in rows
    ], dtype=object)
    y_values = {
        target: np.asarray([float(row[target]) for row in rows], dtype=float)
        for target in TARGET_COLUMNS
    }
    for target, values in y_values.items():
        if not np.isfinite(values).all() or not np.logical_and(values >= 0, values <= 100).all():
            raise ValueError(f"Target {target} must contain finite percentages between 0 and 100.")

    train_idx, validation_idx, test_idx = split_by_group(groups, seed)
    train_validation_idx = np.concatenate([train_idx, validation_idx])
    X_train = X[train_idx]
    X_validation = X[validation_idx]
    X_train_validation = X[train_validation_idx]
    X_test = X[test_idx]
    artifacts = {}
    evaluations = {}

    for target in TARGET_COLUMNS:
        candidate_results = {}
        for name, estimator in candidate_estimators(seed).items():
            candidate = make_pipeline(estimator)
            candidate.fit(X_train, y_values[target][train_idx])
            candidate_results[name] = {
                "model": candidate,
                "validation_metrics": calculate_metrics(
                    y_values[target][validation_idx], candidate.predict(X_validation)
                ),
            }

        selected_name = min(
            candidate_results,
            key=lambda name: (candidate_results[name]["validation_metrics"]["mae"], name),
        )
        baseline_name = "dummy_mean"
        selected_pipeline = make_pipeline(candidate_estimators(seed)[selected_name])
        baseline_pipeline = make_pipeline(candidate_estimators(seed)[baseline_name])
        selected_pipeline.fit(X_train_validation, y_values[target][train_validation_idx])
        baseline_pipeline.fit(X_train_validation, y_values[target][train_validation_idx])
        selected_test = calculate_metrics(y_values[target][test_idx], selected_pipeline.predict(X_test))
        baseline_test = calculate_metrics(y_values[target][test_idx], baseline_pipeline.predict(X_test))
        meaningful = selected_name != baseline_name and selected_test["mae"] <= baseline_test["mae"] * 0.95
        artifacts[target] = selected_pipeline
        evaluations[target] = {
            "selected_model": selected_name,
            "selection_rule": "Lowest validation MAE among DummyRegressor, LinearRegression, and RandomForestRegressor.",
            "validation_metrics_by_model": {
                name: result["validation_metrics"] for name, result in candidate_results.items()
            },
            "test_metrics": selected_test,
            "baseline_model": baseline_name,
            "baseline_test_metrics": baseline_test,
            "meaningful_improvement_over_baseline": meaningful,
            "meaningful_improvement_rule": "Selected test MAE is at least 5% lower than baseline test MAE.",
        }

    output_root = output_root.resolve()
    version_dir = output_root / version_name
    if version_dir.exists():
        raise FileExistsError(f"Model version already exists and will not be overwritten: {version_dir}")
    output_root.mkdir(parents=True, exist_ok=True)
    version_dir.mkdir()

    model_path = version_dir / "campaign_performance_pipelines.joblib"
    metrics_path = version_dir / "metrics.json"
    copied_metadata_path = version_dir / "dataset_metadata.json"
    joblib.dump({"version": version_name, "feature_schema": FEATURES, "models": artifacts}, model_path, compress=3)
    metrics_document = {
        "status": "synthetic_experiment_only",
        "dataset_type": "synthetic",
        "dataset_version": dataset_metadata["dataset_version"],
        "dataset_sha256": dataset_metadata["dataset_sha256"],
        "targets": TARGETS,
        "target_units": {target: "percent" for target in TARGET_COLUMNS},
        "feature_schema": FEATURES,
        "features_excluded_for_leakage": sorted(FORBIDDEN_FEATURES),
        "split_strategy": {
            "name": "GroupShuffleSplit, groups held out across train, validation, and test",
            "train_rows": len(train_idx),
            "validation_rows": len(validation_idx),
            "test_rows": len(test_idx),
            "train_groups": int(np.unique(groups[train_idx]).size),
            "validation_groups": int(np.unique(groups[validation_idx]).size),
            "test_groups": int(np.unique(groups[test_idx]).size),
            "seed": seed,
        },
        "evaluation": evaluations,
        "prediction_bounds": {
            "strategy": "Clip finite estimator outputs to the mathematically valid interval [0, 100] percent.",
            "clipping_implies_accuracy": False,
        },
        "limitations": [
            "All training and evaluation targets are synthetic and based on assumptions in the dataset generator.",
            "Held-out synthetic metrics do not estimate accuracy on real advertising campaigns.",
            "A numerical prediction is not evidence that a campaign will achieve that rate.",
        ],
    }
    metrics_path.write_text(json.dumps(metrics_document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    shutil.copyfile(metadata_path, copied_metadata_path)
    dependencies = {}
    for package in ("scikit-learn", "joblib", "numpy", "scipy"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = "unavailable"
    manifest = {
        "artifact_status": "synthetic_experiment_only",
        "artifact_trust": "Trusted local output created by train_model.py; never load arbitrary pickle/joblib files.",
        "model_version": version_name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "synthetic_data": True,
        "feature_schema": FEATURES,
        "targets": list(TARGET_COLUMNS),
        "selected_models": {target: evaluations[target]["selected_model"] for target in TARGET_COLUMNS},
        "dataset_sha256": dataset_metadata["dataset_sha256"],
        "dependency_versions": dependencies,
        "python_version": platform.python_version(),
        "files": {
            model_path.name: _sha256(model_path),
            metrics_path.name: _sha256(metrics_path),
            copied_metadata_path.name: _sha256(copied_metadata_path),
        },
    }
    (version_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    active_temp = output_root / "active.json.tmp"
    active_temp.write_text(json.dumps({"model_version": version_name}, indent=2) + "\n", encoding="utf-8")
    active_temp.replace(output_root / "active.json")
    return {"version_dir": version_dir, "manifest": manifest, "metrics": metrics_document}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--version", default="campaign-performance-v1")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = train_experiment(args.dataset, args.output_root, args.version, args.seed)
    print(f"Saved model version {args.version} to {result['version_dir']}")
    for target, evaluation in result["metrics"]["evaluation"].items():
        print(f"{target}: selected={evaluation['selected_model']}, test={evaluation['test_metrics']}, baseline={evaluation['baseline_test_metrics']}")
        print(f"Meaningful improvement over baseline: {evaluation['meaningful_improvement_over_baseline']}")


if __name__ == "__main__":
    main()
