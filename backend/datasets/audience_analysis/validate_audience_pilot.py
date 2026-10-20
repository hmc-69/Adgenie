#!/usr/bin/env python3
"""
Validate the AdGenie audience-analysis pilot CSV.

Usage:
    python validate_audience_pilot.py path/to/adgenie_audience_pilot_filled_template.csv

This validates structure and data hygiene. It does NOT verify that proposed labels
are correct or that synthetic labels are suitable ground truth for model training.
"""
pip install pandas
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

EXPECTED_COLUMNS = [
    "example_id",
    "campaign_group_id",
    "product_name",
    "description",
    "platform",
    "objective",
    "tone",
    "keywords",
    "dominant_archetype",
    "annotator_1_label",
    "annotator_2_label",
    "adjudicated_label",
    "source_reference",
    "license_or_permission",
    "annotation_status",
]

ALLOWED_LABELS = {
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

EXPECTED_PILOT_ROWS_PER_CLASS = 5
SYNTHETIC_STATUS = "synthetic_ai_proposed_not_human_validated"
REQUIRED_NONEMPTY = [
    "example_id",
    "campaign_group_id",
    "product_name",
    "description",
    "platform",
    "objective",
    "tone",
    "keywords",
    "dominant_archetype",
    "source_reference",
    "license_or_permission",
    "annotation_status",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("C:/Users/heman/Downloads/adgenie_audience_pilot_filled_template.csv", type=Path, help="Path to the pilot CSV")
    parser.add_argument(
        "--strict-pilot",
        action="store_true",
        help="Require exactly 45 rows and exactly 5 rows per archetype",
    )
    args = parser.parse_args()

    if not args.csv_path.exists():
        print(f"ERROR: File not found: {args.csv_path}", file=sys.stderr)
        return 2

    try:
        df = pd.read_csv(args.csv_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as exc:
        print(f"ERROR: Could not read CSV: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    # Exact schema and order.
    actual_columns = list(df.columns)
    if actual_columns != EXPECTED_COLUMNS:
        if set(actual_columns) == set(EXPECTED_COLUMNS):
            errors.append("Columns exist but are not in the required order.")
        else:
            missing = [c for c in EXPECTED_COLUMNS if c not in actual_columns]
            extra = [c for c in actual_columns if c not in EXPECTED_COLUMNS]
            if missing:
                errors.append(f"Missing columns: {missing}")
            if extra:
                errors.append(f"Unexpected columns: {extra}")

    if df.empty:
        errors.append("CSV contains no data rows.")

    # Check required fields.
    for col in REQUIRED_NONEMPTY:
        if col in df.columns:
            mask = df[col].astype(str).str.strip().eq("")
            if mask.any():
                errors.append(f"{col}: {int(mask.sum())} blank value(s).")

    # Unique IDs.
    if "example_id" in df.columns:
        ids = df["example_id"].astype(str).str.strip()
        duplicate_ids = ids[ids.duplicated(keep=False)].unique().tolist()
        if duplicate_ids:
            errors.append(f"Duplicate example_id values: {duplicate_ids[:10]}")

    # Labels.
    if "dominant_archetype" in df.columns:
        labels = df["dominant_archetype"].astype(str).str.strip()
        invalid = sorted(set(labels) - ALLOWED_LABELS)
        if invalid:
            errors.append(f"Invalid dominant_archetype label(s): {invalid}")
        missing_classes = sorted(ALLOWED_LABELS - set(labels))
        if missing_classes:
            errors.append(f"Missing archetype class(es): {missing_classes}")
        counts = labels.value_counts().to_dict()
        print("Class distribution:")
        for label in sorted(ALLOWED_LABELS):
            print(f"  {label}: {counts.get(label, 0)}")
        if args.strict_pilot:
            if len(df) != 45:
                errors.append(f"Strict pilot expects 45 rows; found {len(df)}.")
            uneven = {label: counts.get(label, 0) for label in ALLOWED_LABELS
                      if counts.get(label, 0) != EXPECTED_PILOT_ROWS_PER_CLASS}
            if uneven:
                errors.append(f"Strict pilot expects 5 rows per class; mismatches: {uneven}")

    # Review fields are not considered proof of human review; check status explicitly.
    if "annotation_status" in df.columns:
        statuses = df["annotation_status"].astype(str).str.strip()
        if (statuses == SYNTHETIC_STATUS).all():
            warnings.append(
                "All rows are synthetic AI proposals, not human-validated ground truth. "
                "Use for schema/pipeline smoke tests only."
            )
        elif statuses.str.contains("synthetic", case=False, na=False).any():
            warnings.append(
                "Some rows are marked synthetic. Keep synthetic and verified data distinguishable."
            )
        else:
            warnings.append(
                "No synthetic status marker detected. Confirm provenance and review status manually."
            )

    # Duplicate brief detection (normalizes case/whitespace only).
    if {"product_name", "description"}.issubset(df.columns):
        normalized = (
            df["product_name"].str.strip().str.lower()
            + " | "
            + df["description"].str.strip().str.lower()
        )
        dup_mask = normalized.duplicated(keep=False)
        if dup_mask.any():
            warnings.append(
                f"Found {int(dup_mask.sum())} rows with duplicate product-name/description pairs."
            )

    # Reused campaign groups can be intentional; flag for human review rather than fail.
    if {"campaign_group_id", "dominant_archetype"}.issubset(df.columns):
        cross_label = df.groupby("campaign_group_id")["dominant_archetype"].nunique()
        groups = cross_label[cross_label > 1].index.tolist()
        if groups:
            warnings.append(
                "Campaign group(s) contain multiple labels. Verify this is intentional: "
                + ", ".join(groups[:10])
            )

    # Annotation columns: don't require them to be blank, but flag synthetic copied labels.
    annotation_cols = [
        c for c in ("annotator_1_label", "annotator_2_label", "adjudicated_label")
        if c in df.columns
    ]
    if len(annotation_cols) == 3 and not df.empty:
        same_as_proposed = True
        for col in annotation_cols:
            if not (df[col].astype(str).str.strip() == df["dominant_archetype"].astype(str).str.strip()).all():
                same_as_proposed = False
                break
        if same_as_proposed:
            warnings.append(
                "All annotation/adjudication labels match the AI proposal. This does not establish "
                "independent annotation or adjudication."
            )

    print(f"\nFile: {args.csv_path}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(actual_columns)}")

    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("\nVALIDATION FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("\nSTRUCTURAL VALIDATION PASSED")
    print("Note: structural validity does not mean labels are scientifically validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
