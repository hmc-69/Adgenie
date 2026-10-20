import csv
import tempfile
import unittest
from pathlib import Path

from assess_audience_dataset import analyze_csv
from generate_synthetic_audience_drafts import CSV_COLUMNS, generate_drafts
from validate_real_campaign_briefs import (
    APPROVED_ARCHETYPES,
    TEMPLATE_PATH,
    validate_csv,
    validate_records,
)


def real_row(**overrides):
    row = {column: "" for column in CSV_COLUMNS}
    row.update({
        "example_id": "REAL-001",
        "campaign_group_id": "campaign-family-1",
        "product_name": "Sample product",
        "description": "A real-source campaign brief for independent human review.",
        "platform": "Instagram",
        "objective": "Brand Awareness",
        "tone": "Friendly",
        "keywords": "sample; review",
        "annotation_status": "annotation_pending",
    })
    row.update(overrides)
    return row


class RealAudienceDataWorkflowTests(unittest.TestCase):
    def test_real_template_has_exact_schema_and_order(self):
        with TEMPLATE_PATH.open("r", newline="", encoding="utf-8-sig") as stream:
            header = next(csv.reader(stream))
        self.assertEqual(tuple(header), CSV_COLUMNS)
        self.assertEqual(len(header), 15)

    def test_synthetic_generator_rows_are_rejected(self):
        generated = generate_drafts(1, seed=3)
        report = validate_records(CSV_COLUMNS, [generated[0]])
        self.assertFalse(report["valid"])
        self.assertTrue(any("synthetic examples" in error for error in report["errors"]))
        self.assertTrue(any("permission is missing or unresolved" in warning for warning in report["warnings"]))

    def test_new_synthetic_permission_marker_is_rejected_even_without_other_markers(self):
        row = real_row(
            example_id="REAL-LOOKING-ID",
            source_reference="source-record:synthetic-test",
            license_or_permission="Synthetic draft; not validated for production use",
            annotation_status="annotation_pending",
        )
        report = validate_records(CSV_COLUMNS, [row])
        self.assertFalse(report["valid"])
        self.assertTrue(any("synthetic examples" in error for error in report["errors"]))
        self.assertTrue(any("permission is missing or unresolved" in warning for warning in report["warnings"]))

    def test_missing_source_or_unresolved_permission_warns_and_blocks_approval(self):
        row = real_row()
        report = validate_records(CSV_COLUMNS, [row])
        self.assertTrue(report["valid"])
        self.assertTrue(any("source_reference is missing" in warning for warning in report["warnings"]))
        self.assertTrue(any("permission is missing or unresolved" in warning for warning in report["warnings"]))

        approved = real_row(
            annotation_status="approved_for_production",
            adjudicated_label="quality_seekers",
            dominant_archetype="quality_seekers",
            license_or_permission="pending",
        )
        report = validate_records(CSV_COLUMNS, [approved])
        self.assertFalse(report["valid"])
        self.assertTrue(any("source_reference" in error for error in report["errors"]))
        self.assertTrue(any("verified permission" in error for error in report["errors"]))

        documented = real_row(
            example_id="REAL-APPROVED-001",
            source_reference="source-record:campaign-42",
            license_or_permission="verified: written campaign-owner permission; evidence: record:permission-42",
            annotation_status="approved_for_production",
            annotator_1_label="quality_seekers",
            annotator_2_label="quality_seekers",
            adjudicated_label="quality_seekers",
            dominant_archetype="quality_seekers",
        )
        report = validate_records(CSV_COLUMNS, [documented])
        self.assertTrue(report["valid"], report["errors"])

    def test_invalid_archetypes_are_rejected(self):
        row = real_row(annotator_1_label="young_professionals")
        report = validate_records(CSV_COLUMNS, [row])
        self.assertFalse(report["valid"])
        self.assertTrue(any("non-approved archetype" in error for error in report["errors"]))
        self.assertEqual(len(APPROVED_ARCHETYPES), 9)

    def test_annotator_and_adjudicated_labels_are_not_conflated(self):
        row = real_row(
            annotation_status="independently_annotated",
            annotator_1_label="quality_seekers",
            annotator_2_label="quality_seekers",
        )
        before = dict(row)
        report = validate_records(CSV_COLUMNS, [row])
        self.assertTrue(report["valid"])
        self.assertEqual(row, before)
        self.assertEqual(row["adjudicated_label"], "")
        self.assertEqual(row["dominant_archetype"], "")

        conflated = real_row(
            annotation_status="adjudicated",
            annotator_1_label="quality_seekers",
            annotator_2_label="quality_seekers",
            adjudicated_label="quality_seekers",
            dominant_archetype="value_seekers",
        )
        report = validate_records(CSV_COLUMNS, [conflated])
        self.assertFalse(report["valid"])
        self.assertTrue(any("must match adjudicated_label" in error for error in report["errors"]))

    def test_assessment_reports_quality_without_modifying_input(self):
        fields = ["campaign_id", "description", "label", "clicks", "email", "source_reference", "annotation_status"]
        rows = [
            {"campaign_id": "c1", "description": "Brief text describing a campaign offer.", "label": "quality_seekers", "clicks": "3", "email": "person@example.com", "source_reference": "", "annotation_status": "pending"},
            {"campaign_id": "c2", "description": "Brief text describing a campaign offer.", "label": "unknown", "clicks": "4", "email": "", "source_reference": "", "annotation_status": "pending"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            before = path.read_bytes()
            report = analyze_csv(path, label_column="label", group_column="campaign_id")
            self.assertEqual(path.read_bytes(), before)

        self.assertEqual(report["row_count"], 2)
        self.assertEqual(report["column_count"], len(fields))
        self.assertEqual(report["candidate_label_report"]["class_counts"], {"quality_seekers": 1, "unknown": 1})
        self.assertFalse(report["candidate_label_report"]["labels_match_approved_archetypes"])
        self.assertEqual(report["likely_duplicate_campaign_briefs"], 1)
        self.assertEqual(report["description_duplicate_count"], 1)
        self.assertEqual(report["near_duplicate_descriptions"]["pair_count"], 0)
        self.assertEqual(report["campaign_grouping"]["class_distribution"]["quality_seekers"]["distinct_group_count"], 1)
        self.assertEqual(report["provenance_and_status_counts"]["source_reference"]["<missing>"], 2)
        self.assertIn("distinctive_label_linked_terms", report["potential_label_leakage"])
        self.assertTrue(report["campaign_grouping"]["can_establish_groups"])
        self.assertIn("email", report["potential_sensitive_columns"])
        self.assertIn("clicks", report["potential_target_leakage_or_post_campaign_fields"])

    def test_assessor_flags_near_duplicate_descriptions_without_returning_text(self):
        fields = ["description", "campaign_group_id"]
        rows = [
            {"description": "A compact kitchen tool stores prepared ingredients in matching containers for a weekday meal plan.", "campaign_group_id": "family-1"},
            {"description": "A compact kitchen tool stores prepared ingredients in matching containers for a weekday meal plans.", "campaign_group_id": "family-1"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "near.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            report = analyze_csv(path, group_column="campaign_group_id")
        self.assertEqual(report["near_duplicate_descriptions"]["pair_count"], 1)
        self.assertNotIn("A compact kitchen tool stores prepared ingredients", str(report["near_duplicate_descriptions"]))

    def test_repeated_prefix_is_distinct_from_exact_and_near_duplicates(self):
        fields = ["description", "campaign_group_id", "label"]
        rows = [
            {"description": "A shared opening phrase has several distinctive words after the prefix, including apples, pears, plums, and apricots.", "campaign_group_id": "family-1", "label": "general_interest"},
            {"description": "A shared opening phrase has several distinctive words after the prefix, including engines, radios, lamps, and cables.", "campaign_group_id": "family-1", "label": "general_interest"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prefix.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            report = analyze_csv(path, label_column="label", group_column="campaign_group_id")
        self.assertEqual(report["description_duplicate_count"], 0)
        self.assertEqual(report["near_duplicate_descriptions"]["pair_count"], 0)
        self.assertEqual(report["potential_label_leakage"]["repeated_description_prefix_count"], 1)

    def test_reordered_identical_word_sets_are_still_near_duplicates(self):
        fields = ["description", "campaign_group_id", "label"]
        rows = [
            {"description": "Campaign brief features a compact travel organizer with labeled compartments for packing.", "campaign_group_id": "family-1", "label": "general_interest"},
            {"description": "Campaign brief features a compact organizer with labeled compartments for packing travel.", "campaign_group_id": "family-1", "label": "general_interest"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reordered-near.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            report = analyze_csv(path, label_column="label", group_column="campaign_group_id")
        self.assertEqual(report["description_duplicate_count"], 0)
        self.assertEqual(report["near_duplicate_descriptions"]["pair_count"], 1)

    def test_validation_csv_does_not_modify_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "real.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                writer.writerow(real_row())
            before = path.read_bytes()
            report = validate_csv(path)
            self.assertEqual(path.read_bytes(), before)
            self.assertTrue(report["valid"])


if __name__ == "__main__":
    unittest.main()
