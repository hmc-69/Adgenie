#!/usr/bin/env python3
"""Train and evaluate an offline, experimental audience-archetype classifier.

Artifacts produced here are trusted local joblib files. This script never loads
an existing pickle/joblib artifact and is not connected to production inference.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = SCRIPT_DIR / "synthetic_audience_drafts.csv"
EXPERIMENT_ROOT = SCRIPT_DIR / "experimental_output"
FEATURE_COLUMNS = ("product_name", "description", "platform", "objective", "tone", "keywords")
GROUP_COLUMN = "campaign_group_id"
TARGET_DEFAULT = "dominant_archetype"
ALLOWED_LABELS = frozenset({
    "convenience_seekers", "value_seekers", "quality_seekers", "style_seekers",
    "learning_seekers", "business_utility_seekers", "hobby_interest_seekers",
    "gift_shoppers", "general_interest",
})
FORBIDDEN_FEATURE_COLUMNS = frozenset({
    "example_id", "campaign_group_id", "source_reference", "license_or_permission",
    "annotator_1_label", "annotator_2_label", "adjudicated_label", "dominant_archetype",
    "ad_target_audience",
})
SYNTHETIC_STATUS = "synthetic_ai_proposed_not_human_validated"
SYNTHETIC_SOURCE = "Synthetic generated draft; no external source"
SYNTHETIC_LICENSES = frozenset({
    "Synthetic draft; review before production use",  # previously generated drafts
    "Synthetic draft; not validated for production use",  # current generator marker
})


class DatasetError(ValueError):
    """Raised when the selected dataset cannot support a valid experiment."""


def runtime_version_fields() -> dict[str, str | dict[str, str]]:
    """Return Python and installed ML runtime dependency versions for the manifest."""
    from importlib.metadata import PackageNotFoundError, version

    distributions = (
        "scikit-learn", "joblib", "numpy", "scipy", "threadpoolctl", "cloudpickle",
    )
    dependency_versions: dict[str, str] = {}
    for distribution in distributions:
        try:
            dependency_versions[distribution] = version(distribution)
        except PackageNotFoundError as exc:
            raise RuntimeError(
                f"Required experiment dependency {distribution!r} is missing; "
                "install the pinned requirements-experimental.txt in the experiment venv."
            ) from exc
    return {
        "python_version": platform.python_version(),
        "dependency_versions": dependency_versions,
    }


def load_dataset(path: Path) -> tuple[list[dict[str, str]], str]:
    path = Path(path)
    try:
        raw = path.read_bytes()
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise DatasetError("Dataset is empty or has no CSV header.")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise DatasetError(f"Could not read dataset CSV: {path}") from exc
    return rows, hashlib.sha256(raw).hexdigest()


def validate_rows(
    rows: list[dict[str, str]], target_column: str, allow_synthetic_labels: bool
) -> list[str]:
    if not rows:
        raise DatasetError("Dataset contains no data rows.")
    if target_column not in {"dominant_archetype", "adjudicated_label"}:
        raise DatasetError("Target must be dominant_archetype or adjudicated_label; audience and identifier fields are not targets.")
    required = set(FEATURE_COLUMNS) | {GROUP_COLUMN, target_column}
    missing_columns = sorted(required - set(rows[0]))
    if missing_columns:
        raise DatasetError(f"Dataset is missing required columns: {', '.join(missing_columns)}")
    missing_labels = [i + 2 for i, row in enumerate(rows) if not (row.get(target_column) or "").strip()]
    if missing_labels:
        raise DatasetError(f"Target column {target_column!r} has missing labels on CSV rows: {missing_labels[:10]}.")
    labels = [(row.get(target_column) or "").strip() for row in rows]
    invalid = sorted(set(labels) - ALLOWED_LABELS)
    if invalid:
        raise DatasetError(f"Target column {target_column!r} has invalid labels: {invalid}.")
    if len(set(labels)) < 2:
        raise DatasetError("Training requires at least two distinct target classes.")
    if any(not (row.get(GROUP_COLUMN) or "").strip() for row in rows):
        raise DatasetError(f"Every row must have a non-empty {GROUP_COLUMN} for group-isolated splitting.")
    if any(not " ".join((row.get(column) or "").strip() for column in FEATURE_COLUMNS).strip() for row in rows):
        raise DatasetError("Every row must contain text in at least one configured feature column.")

    is_synthetic = any(
        row.get("annotation_status") == SYNTHETIC_STATUS
        or row.get("source_reference") == SYNTHETIC_SOURCE
        or row.get("license_or_permission") in SYNTHETIC_LICENSES
        for row in rows
    )
    if is_synthetic:
        if target_column != "dominant_archetype":
            raise DatasetError("Synthetic drafts may only use their provisional dominant_archetype labels.")
        if not allow_synthetic_labels:
            raise DatasetError(
                "Synthetic provisional labels are not ground truth. Re-run with --allow-synthetic-labels "
                "only for an explicitly synthetic pipeline smoke experiment."
            )
        if not all(
            row.get("annotation_status") == SYNTHETIC_STATUS
            and row.get("source_reference") == SYNTHETIC_SOURCE
            and row.get("license_or_permission") in SYNTHETIC_LICENSES
            for row in rows
        ):
            raise DatasetError("Synthetic dataset markers are inconsistent; refusing to train on mixed provenance.")

    return sorted(set(labels))


def validate_feature_columns(feature_columns: Sequence[str] = FEATURE_COLUMNS) -> tuple[str, ...]:
    columns = tuple(feature_columns)
    if not columns or len(set(columns)) != len(columns):
        raise DatasetError("Feature columns must be a non-empty list without duplicates.")
    forbidden = sorted(set(columns) & FORBIDDEN_FEATURE_COLUMNS)
    if forbidden:
        raise DatasetError(f"Leakage-prone identifier, provenance, or label columns cannot be features: {forbidden}.")
    if set(columns) - set(FEATURE_COLUMNS):
        raise DatasetError(f"Only approved campaign text features are allowed: {FEATURE_COLUMNS}.")
    return columns


def grouped_stratified_holdout(
    rows: list[dict[str, str]], labels: Sequence[str], seed: int, test_fraction: float = 0.2,
    attempts: int = 4096,
) -> tuple[list[int], list[int]]:
    """Find a deterministic group-isolated holdout with all labels on both sides."""
    if not 0.1 <= test_fraction <= 0.4:
        raise DatasetError("test_fraction must be between 0.10 and 0.40.")
    group_rows: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        group_rows[row[GROUP_COLUMN].strip()].append(index)
    groups = sorted(group_rows)
    if len(groups) < 3:
        raise DatasetError(
            f"Group-aware train/test evaluation needs at least 3 distinct {GROUP_COLUMN} values; found {len(groups)}."
        )

    label_groups: dict[str, set[str]] = defaultdict(set)
    group_label_counts: dict[str, Counter[str]] = {}
    for group, indexes in group_rows.items():
        counts = Counter(rows[i]["_validated_target"] for i in indexes)
        group_label_counts[group] = counts
        for label in counts:
            label_groups[label].add(group)
    infeasible = {label: len(label_groups[label]) for label in labels if len(label_groups[label]) < 2}
    if infeasible:
        raise DatasetError(
            "Group-aware stratification is infeasible: each class must occur in at least two distinct groups; "
            f"found {infeasible}. Add independently labeled examples in more groups or revise the target."
        )

    overall_counts = Counter(row["_validated_target"] for row in rows)
    total = len(rows)
    target_size = total * test_fraction
    group_count = len(groups)
    candidate_sizes = sorted({
        max(1, min(group_count - 1, round(group_count * test_fraction) + offset))
        for offset in range(-2, 3)
    })
    rng = random.Random(seed)
    best: tuple[float, list[int], list[int]] | None = None

    for _ in range(attempts):
        shuffled = groups[:]
        rng.shuffle(shuffled)
        for count in candidate_sizes:
            test_groups = set(shuffled[:count])
            test_indexes = [i for group in test_groups for i in group_rows[group]]
            train_indexes = [i for group in groups if group not in test_groups for i in group_rows[group]]
            test_counts = Counter(rows[i]["_validated_target"] for i in test_indexes)
            train_counts = Counter(rows[i]["_validated_target"] for i in train_indexes)
            if any(test_counts[label] == 0 or train_counts[label] == 0 for label in labels):
                continue
            size_error = abs(len(test_indexes) - target_size) / total
            class_error = sum(
                abs(test_counts[label] / len(test_indexes) - overall_counts[label] / total)
                for label in labels
            ) / len(labels)
            score = size_error + class_error
            if best is None or score < best[0]:
                best = (score, sorted(train_indexes), sorted(test_indexes))
        if best is not None and best[0] < 0.005:
            break

    if best is None:
        raise DatasetError(
            "Could not create a group-isolated stratified holdout with every class represented in train and test. "
            "Add more labeled campaign groups per class or collect a dataset with broader class coverage; "
            "no row-level random split was attempted."
        )
    return best[1], best[2]


def stratified_row_holdout(
    rows: list[dict[str, str]], labels: Sequence[str], seed: int, test_fraction: float = 0.2
) -> tuple[list[int], list[int]]:
    """Create a deterministic row-level stratified split for comparison only."""
    if not 0.1 <= test_fraction <= 0.4:
        raise DatasetError("test_fraction must be between 0.10 and 0.40.")
    label_rows: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        label_rows[row["_validated_target"]].append(index)
    missing = {label: len(label_rows[label]) for label in labels if len(label_rows[label]) < 2}
    if missing:
        raise DatasetError(f"Row-stratified holdout needs at least two examples per class; found {missing}.")
    rng = random.Random(seed)
    train_indexes: list[int] = []
    test_indexes: list[int] = []
    for label in labels:
        indexes = label_rows[label][:]
        rng.shuffle(indexes)
        test_count = max(1, min(len(indexes) - 1, round(len(indexes) * test_fraction)))
        test_indexes.extend(indexes[:test_count])
        train_indexes.extend(indexes[test_count:])
    return sorted(train_indexes), sorted(test_indexes)


def _texts(rows: list[dict[str, str]], indexes: Sequence[int], columns: Sequence[str]) -> list[str]:
    return [" ".join((rows[i].get(column) or "").strip() for column in columns) for i in indexes]


def _counts(rows: list[dict[str, str]], indexes: Sequence[int]) -> dict[str, int]:
    return dict(sorted(Counter(rows[i]["_validated_target"] for i in indexes).items()))


def _metric_report(y_true, y_pred, labels: Sequence[str]) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )

    report = classification_report(y_true, y_pred, labels=list(labels), output_dict=True, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_precision": float(precision_score(y_true, y_pred, labels=list(labels), average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_true, y_pred, labels=list(labels), average="macro", zero_division=0)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=list(labels), average="macro", zero_division=0)),
        "per_class": {
            label: {
                metric: float(report[label][metric])
                for metric in ("precision", "recall", "f1-score", "support")
            }
            for label in labels
        },
        "confusion_matrix_labels": list(labels),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(labels)).tolist(),
    }


def train_experiment(
    dataset_path: Path = DEFAULT_DATASET,
    target_column: str = TARGET_DEFAULT,
    seed: int = 42,
    allow_synthetic_labels: bool = False,
    test_fraction: float = 0.2,
) -> Path:
    rows, dataset_sha256 = load_dataset(Path(dataset_path))
    labels = validate_rows(rows, target_column, allow_synthetic_labels)
    feature_columns = validate_feature_columns(FEATURE_COLUMNS)
    for row in rows:
        row["_validated_target"] = (row.get(target_column) or "").strip()
    group_train_indexes, group_test_indexes = grouped_stratified_holdout(rows, labels, seed, test_fraction)
    row_train_indexes, row_test_indexes = stratified_row_holdout(rows, labels, seed, test_fraction)

    try:
        from joblib import dump
        from sklearn.dummy import DummyClassifier
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "Experimental training requires scikit-learn and joblib, which are not installed in the active "
            f"interpreter ({sys.version.split()[0]}). Install them only in a dedicated experimental environment; "
            "the project backend requirements/runtime were not changed."
        ) from exc

    version_fields = runtime_version_fields()

    vectorizer_params = {"ngram_range": [1, 2], "min_df": 1, "max_features": 20000, "strip_accents": "unicode"}
    classifier_params = {"C": 1.0, "max_iter": 1000, "class_weight": None, "random_state": seed}

    synthetic = allow_synthetic_labels and any(row.get("annotation_status") == SYNTHETIC_STATUS for row in rows)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = EXPERIMENT_ROOT / f"{'synthetic-' if synthetic else ''}run-{timestamp}-seed-{seed}"
    run_dir.mkdir(parents=True, exist_ok=False)
    split_indexes = {
        "group_aware": (group_train_indexes, group_test_indexes),
        "row_stratified": (row_train_indexes, row_test_indexes),
    }
    evaluations: dict[str, dict] = {}
    for split_name, (train_indexes, test_indexes) in split_indexes.items():
        y_train = [rows[i]["_validated_target"] for i in train_indexes]
        y_test = [rows[i]["_validated_target"] for i in test_indexes]
        x_train = _texts(rows, train_indexes, feature_columns)
        x_test = _texts(rows, test_indexes, feature_columns)
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(**{**vectorizer_params, "ngram_range": tuple(vectorizer_params["ngram_range"])})),
            ("classifier", LogisticRegression(**classifier_params)),
        ])
        baseline = DummyClassifier(strategy="most_frequent")
        pipeline.fit(x_train, y_train)
        baseline.fit(["constant"] * len(y_train), y_train)
        y_pred = pipeline.predict(x_test)
        baseline_pred = baseline.predict(["constant"] * len(y_test))
        model_filename = "tfidf_logistic_regression.joblib" if split_name == "group_aware" else "tfidf_logistic_regression_row_stratified.joblib"
        dump(pipeline, run_dir / model_filename)
        evaluations[split_name] = {
            "split_method": (
                f"deterministic group-aware stratified holdout; group={GROUP_COLUMN}; test_fraction={test_fraction}; seed={seed}"
                if split_name == "group_aware"
                else f"deterministic per-class row-stratified holdout; test_fraction={test_fraction}; seed={seed}"
            ),
            "split_sizes": {"train": len(train_indexes), "test": len(test_indexes)},
            "split_class_counts": {"train": _counts(rows, train_indexes), "test": _counts(rows, test_indexes)},
            "train_group_count": len({rows[i][GROUP_COLUMN] for i in train_indexes}),
            "test_group_count": len({rows[i][GROUP_COLUMN] for i in test_indexes}),
            "group_overlap_count": len(
                {rows[i][GROUP_COLUMN] for i in train_indexes} & {rows[i][GROUP_COLUMN] for i in test_indexes}
            ),
            "model_artifact": model_filename,
            "model": _metric_report(y_test, y_pred, labels),
            "dummy_most_frequent_baseline": _metric_report(y_test, baseline_pred, labels),
        }
    primary = evaluations["group_aware"]
    metrics = {
        "status": "synthetic_experiment_only" if synthetic else "experimental_unvalidated_data",
        "warning": "Synthetic results are pipeline smoke tests only; they are not real-world performance estimates." if synthetic else "Experimental evaluation only; do not infer production performance.",
        "dataset_rows": len(rows),
        "dataset_class_counts": dict(sorted(Counter(row["_validated_target"] for row in rows).items())),
        # Preserve the original top-level fields as aliases for the primary, group-aware evaluation.
        "split_sizes": primary["split_sizes"],
        "split_class_counts": primary["split_class_counts"],
        "model": primary["model"],
        "dummy_most_frequent_baseline": primary["dummy_most_frequent_baseline"],
        "primary_evaluation": "group_aware",
        "evaluations": evaluations,
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    class_mapping = {label: index for index, label in enumerate(labels)}
    manifest = {
        "status": "synthetic_experiment_only" if synthetic else "experimental_unvalidated_data",
        "dataset_path": str(Path(dataset_path).resolve()),
        "dataset_sha256": dataset_sha256,
        "seed": seed,
        "feature_columns": list(feature_columns),
        "target_column": target_column,
        "split_method": primary["split_method"],
        "evaluation_splits": {
            name: {key: result[key] for key in ("split_method", "split_sizes", "train_group_count", "test_group_count", "group_overlap_count")}
            for name, result in evaluations.items()
        },
        "split_sizes": metrics["split_sizes"],
        "class_mapping": class_mapping,
        **version_fields,
        # Retained for consumers of the original manifest field.
        "scikit_learn_version": version_fields["dependency_versions"]["scikit-learn"],
        "model_parameters": {
            "vectorizer": vectorizer_params,
            "logistic_regression": classifier_params,
            "baseline": {"strategy": "most_frequent"},
        },
        "artifact_trust": "Trusted local output created by this script. Never load arbitrary pickle/joblib files.",
        "synthetic_labels_explicitly_allowed": allow_synthetic_labels,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return run_dir


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--target-column", default=TARGET_DEFAULT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--allow-synthetic-labels", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_dir = train_experiment(
            args.dataset, args.target_column, args.seed, args.allow_synthetic_labels, args.test_fraction
        )
    except (DatasetError, RuntimeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Saved experimental results to {run_dir}")
    if "synthetic-" in run_dir.name:
        print("SYNTHETIC EXPERIMENT ONLY: metrics are pipeline smoke tests, not real-world performance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
