import csv
import platform
import tempfile
import unittest
from importlib.metadata import version
from pathlib import Path

from train_audience_classifier import (
    ALLOWED_LABELS,
    FEATURE_COLUMNS,
    DatasetError,
    _metric_report,
    grouped_stratified_holdout,
    runtime_version_fields,
    stratified_row_holdout,
    train_experiment,
    validate_feature_columns,
    validate_rows,
)


def sample_rows(group_count=24):
    labels = sorted(ALLOWED_LABELS)
    rows = []
    for group_index in range(group_count):
        for label_index, label in enumerate(labels):
            rows.append({
                "example_id": f"id-{group_index}-{label_index}",
                "campaign_group_id": f"group-{group_index}",
                "product_name": f"Product {group_index}",
                "description": f"Synthetic context for {label} item {group_index}",
                "platform": "Instagram",
                "objective": "Brand Awareness",
                "tone": "Friendly",
                "keywords": f"keyword {label_index}",
                "dominant_archetype": label,
                "annotator_1_label": "",
                "annotator_2_label": "",
                "adjudicated_label": "",
                "source_reference": "Synthetic generated draft; no external source",
                "license_or_permission": "Synthetic draft; not validated for production use",
                "annotation_status": "synthetic_ai_proposed_not_human_validated",
            })
    return rows


class AudienceTrainingPipelineTests(unittest.TestCase):
    def test_metric_report_includes_requested_macro_and_per_class_metrics(self):
        labels = ["convenience_seekers", "value_seekers"]
        report = _metric_report(
            ["convenience_seekers", "value_seekers", "value_seekers"],
            ["convenience_seekers", "convenience_seekers", "value_seekers"],
            labels,
        )
        self.assertIn("accuracy", report)
        self.assertIn("macro_precision", report)
        self.assertIn("macro_recall", report)
        self.assertIn("macro_f1", report)
        self.assertEqual(set(report["per_class"]), set(labels))
        self.assertEqual(len(report["confusion_matrix"]), len(labels))

    def test_manifest_runtime_versions_match_installed_distributions(self):
        fields = runtime_version_fields()
        self.assertEqual(fields["python_version"], platform.python_version())
        dependencies = fields["dependency_versions"]
        expected_distributions = (
            "scikit-learn", "joblib", "numpy", "scipy", "threadpoolctl", "cloudpickle",
        )
        self.assertEqual(set(dependencies), set(expected_distributions))
        for distribution in expected_distributions:
            with self.subTest(distribution=distribution):
                self.assertEqual(dependencies[distribution], version(distribution))

    def test_rejects_missing_invalid_and_single_class_labels(self):
        rows = sample_rows()
        rows[0]["dominant_archetype"] = ""
        with self.assertRaisesRegex(DatasetError, "missing labels"):
            validate_rows(rows, "dominant_archetype", True)

        rows = sample_rows()
        rows[0]["dominant_archetype"] = "made_up_label"
        with self.assertRaisesRegex(DatasetError, "invalid labels"):
            validate_rows(rows, "dominant_archetype", True)

        rows = sample_rows()
        for row in rows:
            row["dominant_archetype"] = "general_interest"
        with self.assertRaisesRegex(DatasetError, "at least two"):
            validate_rows(rows, "dominant_archetype", True)

    def test_requires_explicit_opt_in_for_synthetic_labels(self):
        rows = sample_rows()
        with self.assertRaisesRegex(DatasetError, "--allow-synthetic-labels"):
            validate_rows(rows, "dominant_archetype", False)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(DatasetError, "--allow-synthetic-labels"):
                train_experiment(path, allow_synthetic_labels=False)

        # Older draft files remain recognizable, while still requiring explicit opt-in.
        legacy_rows = sample_rows()
        for row in legacy_rows:
            row["license_or_permission"] = "Synthetic draft; review before production use"
        self.assertEqual(set(validate_rows(legacy_rows, "dominant_archetype", True)), set(ALLOWED_LABELS))

    def test_rejects_mixed_synthetic_provenance(self):
        rows = sample_rows()
        rows[-1]["annotation_status"] = "adjudicated"
        with self.assertRaisesRegex(DatasetError, "markers are inconsistent"):
            validate_rows(rows, "dominant_archetype", True)

    def test_feature_columns_exclude_identifiers_labels_and_provenance(self):
        self.assertEqual(validate_feature_columns(), FEATURE_COLUMNS)
        for forbidden in (
            "campaign_group_id", "example_id", "source_reference", "annotator_1_label",
            "adjudicated_label", "dominant_archetype", "ad_target_audience",
        ):
            with self.subTest(column=forbidden), self.assertRaisesRegex(DatasetError, "cannot be features"):
                validate_feature_columns(("description", forbidden))

    def test_group_split_is_isolated_reproducible_and_class_covered(self):
        rows = sample_rows()
        for row in rows:
            row["_validated_target"] = row["dominant_archetype"]
        labels = sorted(ALLOWED_LABELS)
        train_a, test_a = grouped_stratified_holdout(rows, labels, seed=14)
        train_b, test_b = grouped_stratified_holdout(rows, labels, seed=14)
        self.assertEqual((train_a, test_a), (train_b, test_b))
        train_groups = {rows[index]["campaign_group_id"] for index in train_a}
        test_groups = {rows[index]["campaign_group_id"] for index in test_a}
        self.assertFalse(train_groups & test_groups)
        self.assertEqual({rows[i]["_validated_target"] for i in train_a}, set(labels))
        self.assertEqual({rows[i]["_validated_target"] for i in test_a}, set(labels))

    def test_row_stratified_split_is_reproducible_and_balanced_by_class(self):
        rows = sample_rows()
        for row in rows:
            row["_validated_target"] = row["dominant_archetype"]
        labels = sorted(ALLOWED_LABELS)
        train_a, test_a = stratified_row_holdout(rows, labels, seed=12, test_fraction=0.2)
        self.assertEqual((train_a, test_a), stratified_row_holdout(rows, labels, seed=12, test_fraction=0.2))
        self.assertEqual({rows[i]["_validated_target"] for i in train_a}, set(labels))
        self.assertEqual({rows[i]["_validated_target"] for i in test_a}, set(labels))
        self.assertEqual(len(test_a), 5 * len(labels))

    def test_fails_when_group_stratification_is_not_feasible(self):
        rows = sample_rows(group_count=12)
        for row in rows:
            row["_validated_target"] = row["dominant_archetype"]
        rare = "gift_shoppers"
        rare_indexes = [i for i, row in enumerate(rows) if row["_validated_target"] == rare]
        for i in rare_indexes[1:]:
            rows[i]["_validated_target"] = "general_interest"
        with self.assertRaisesRegex(DatasetError, "at least two distinct groups"):
            grouped_stratified_holdout(rows, sorted(ALLOWED_LABELS), seed=1)


if __name__ == "__main__":
    unittest.main()
