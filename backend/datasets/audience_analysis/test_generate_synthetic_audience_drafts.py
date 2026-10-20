import csv
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from generate_synthetic_audience_drafts import (
    APPROVED_ARCHETYPES,
    CSV_COLUMNS,
    LICENSE_OR_PERMISSION,
    PILOT_PATH,
    SYNTHETIC_STATUS,
    TEMPLATE_PATH,
    generate_drafts,
    read_template_columns,
    write_drafts,
)


class SyntheticAudienceDraftTests(unittest.TestCase):
    def test_generation_is_deterministic_for_same_seed(self):
        self.assertEqual(generate_drafts(3, seed=27), generate_drafts(3, seed=27))
        self.assertNotEqual(generate_drafts(3, seed=27), generate_drafts(3, seed=28))

    def test_generates_requested_class_counts_and_unique_ids(self):
        rows = generate_drafts(4, seed=4)
        self.assertEqual(len(rows), 4 * len(APPROVED_ARCHETYPES))
        self.assertEqual(Counter(row["dominant_archetype"] for row in rows), {label: 4 for label in APPROVED_ARCHETYPES})
        self.assertEqual(len({row["example_id"] for row in rows}), len(rows))

    def test_preserves_template_schema_order_and_valid_required_fields(self):
        self.assertEqual(read_template_columns(), CSV_COLUMNS)
        rows = generate_drafts(2, seed=9)
        for row in rows:
            self.assertEqual(tuple(row), CSV_COLUMNS)
            for field in ("product_name", "description", "platform", "objective", "tone", "keywords"):
                self.assertTrue(row[field].strip(), field)

    def test_campaign_groups_are_product_family_based_and_shared_across_labels(self):
        rows = generate_drafts(3, seed=12)
        labels_by_group = {}
        for row in rows:
            labels_by_group.setdefault(row["campaign_group_id"], set()).add(row["dominant_archetype"])
        self.assertEqual(len(labels_by_group), 3)
        self.assertTrue(all(labels == set(APPROVED_ARCHETYPES) for labels in labels_by_group.values()))
        self.assertTrue(all(not any(label in row["campaign_group_id"] for label in APPROVED_ARCHETYPES) for row in rows))

    def test_synthetic_labels_are_proposed_and_human_annotation_fields_stay_blank(self):
        rows = generate_drafts(1)
        for row in rows:
            self.assertEqual(row["source_reference"], "Synthetic generated draft; no external source")
            self.assertEqual(row["license_or_permission"], "Synthetic draft; not validated for production use")
            self.assertEqual(row["annotation_status"], SYNTHETIC_STATUS)
            self.assertIn(row["dominant_archetype"], APPROVED_ARCHETYPES)
            self.assertEqual(row["annotator_1_label"], "")
            self.assertEqual(row["annotator_2_label"], "")
            self.assertEqual(row["adjudicated_label"], "")

    def test_proposed_label_is_not_repeated_in_id_or_keyword_cues(self):
        rows = generate_drafts(12, seed=31)
        for row in rows:
            label = row["dominant_archetype"]
            self.assertNotIn(label, row["example_id"])
            self.assertNotIn(label, row["description"].casefold())

    def test_borderline_examples_are_present_but_still_unvalidated(self):
        rows = generate_drafts(10, seed=44)
        label_rows = [row for row in rows if row["dominant_archetype"] != "general_interest"]
        self.assertEqual(sum("Alongside this," in row["description"] for row in label_rows), len(APPROVED_ARCHETYPES) - 1)
        self.assertTrue(all(row["annotation_status"] == SYNTHETIC_STATUS for row in rows))
        self.assertTrue(all(not row["annotator_1_label"] and not row["annotator_2_label"] and not row["adjudicated_label"] for row in rows))

    def test_destination_is_not_overwritten_without_explicit_option(self):
        rows = generate_drafts(1)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "drafts.csv"
            destination.write_text("keep this file", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_drafts(rows, destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "keep this file")

    def test_human_reviewed_files_and_pilot_are_protected_even_with_overwrite(self):
        rows = generate_drafts(1)
        with tempfile.TemporaryDirectory() as directory:
            human_file = Path(directory) / "reviewed.csv"
            with human_file.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                human_row = dict(rows[0])
                human_row["annotation_status"] = "adjudicated"
                human_row["adjudicated_label"] = human_row["dominant_archetype"]
                writer.writerow(human_row)
            original = human_file.read_bytes()
            with self.assertRaises(ValueError):
                write_drafts(rows, human_file, overwrite=True)
            self.assertEqual(human_file.read_bytes(), original)

            protected_pilot = Path(directory) / PILOT_PATH.name
            protected_pilot.write_text("pilot", encoding="utf-8")
            with self.assertRaises(ValueError):
                write_drafts(rows, protected_pilot, overwrite=True)
            self.assertEqual(protected_pilot.read_text(encoding="utf-8"), "pilot")

    def test_explicit_overwrite_replaces_only_recognized_synthetic_drafts(self):
        rows = generate_drafts(1, seed=3)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "drafts.csv"
            write_drafts(rows, destination)
            replacement = generate_drafts(2, seed=8)
            write_drafts(replacement, destination, overwrite=True)
            with destination.open(newline="", encoding="utf-8") as source:
                saved = list(csv.DictReader(source))
            self.assertEqual(len(saved), 2 * len(APPROVED_ARCHETYPES))
            self.assertTrue(all(row["annotation_status"] == SYNTHETIC_STATUS for row in saved))

    def test_existing_template_and_pilot_are_not_modified(self):
        template_before = TEMPLATE_PATH.read_bytes()
        pilot_before = PILOT_PATH.read_bytes()
        self.assertEqual(TEMPLATE_PATH.read_bytes(), template_before)
        self.assertEqual(PILOT_PATH.read_bytes(), pilot_before)


if __name__ == "__main__":
    unittest.main()
