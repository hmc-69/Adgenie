#!/usr/bin/env python3
"""Validate a real-campaign annotation CSV without importing it into the app."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "real_campaign_briefs_template.csv"
CSV_COLUMNS = (
    "example_id", "campaign_group_id", "product_name", "description", "platform", "objective", "tone",
    "keywords", "dominant_archetype", "annotator_1_label", "annotator_2_label", "adjudicated_label",
    "source_reference", "license_or_permission", "annotation_status",
)
APPROVED_ARCHETYPES = frozenset({
    "convenience_seekers", "value_seekers", "quality_seekers", "style_seekers",
    "learning_seekers", "business_utility_seekers", "hobby_interest_seekers",
    "gift_shoppers", "general_interest",
})
ALLOWED_STATUSES = frozenset({
    "source_review_pending", "permission_review_pending", "annotation_pending",
    "independently_annotated", "adjudication_required", "review_required",
    "adjudicated", "approved_for_production", "rejected",
})
SYNTHETIC_MARKERS = (
    "synthetic generated draft; no external source",
    "synthetic draft; review before production use",
    "synthetic draft; not validated for production use",
    "synthetic_ai_proposed_not_human_validated",
)
APPROVED_PERMISSION_PATTERN = re.compile(
    r"(?i)^verified:\s*[^;]+;\s*evidence:\s*(?:https?://\S+|(?:record|doc|ticket):\S+)\s*$"
)


def validate_records(fieldnames: Sequence[str] | None, rows: list[dict[str, str | None]]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if tuple(fieldnames or ()) != CSV_COLUMNS:
        return {
            "valid": False,
            "row_count": len(rows),
            "errors": ["CSV header must exactly match the real campaign template schema and column order."],
            "warnings": [],
        }

    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        row_errors: list[str] = []
        example_id = (row.get("example_id") or "").strip()
        if not example_id:
            row_errors.append("example_id is missing")
        elif example_id in seen_ids:
            row_errors.append("example_id is duplicated")
        seen_ids.add(example_id)

        source = (row.get("source_reference") or "").strip()
        permission = (row.get("license_or_permission") or "").strip()
        status = (row.get("annotation_status") or "").strip()
        provenance_text = " ".join((example_id, source, permission, status)).casefold()
        if any(marker in provenance_text for marker in SYNTHETIC_MARKERS) or example_id.casefold().startswith("syn-"):
            row_errors.append("synthetic examples are not accepted by the real-data workflow")

        if status and status not in ALLOWED_STATUSES:
            row_errors.append(f"annotation_status {status!r} is not allowed")

        label_fields = ("dominant_archetype", "annotator_1_label", "annotator_2_label", "adjudicated_label")
        for field in label_fields:
            value = (row.get(field) or "").strip()
            if value and value not in APPROVED_ARCHETYPES:
                row_errors.append(f"{field} contains a non-approved archetype")

        adjudicated = (row.get("adjudicated_label") or "").strip()
        dominant = (row.get("dominant_archetype") or "").strip()
        if dominant and not adjudicated:
            row_errors.append("dominant_archetype cannot be populated before adjudication")
        if adjudicated and dominant != adjudicated:
            row_errors.append("dominant_archetype must match adjudicated_label; labels are never copied implicitly")
        if adjudicated and status not in {"adjudicated", "approved_for_production"}:
            row_errors.append("adjudicated_label requires annotation_status 'adjudicated' or 'approved_for_production'")
        if status in {"adjudicated", "approved_for_production"} and not adjudicated:
            row_errors.append(f"{status} status requires an adjudicated_label")
        if status == "rejected":
            warnings.append(f"row {row_number}: record is rejected and is not eligible for model development")
        if status in {"adjudicated", "approved_for_production"} and not (
            (row.get("annotator_1_label") or "").strip() and (row.get("annotator_2_label") or "").strip()
        ):
            warnings.append(f"row {row_number}: one or both independent annotator labels are absent; document why in the annotation log")
        if (
            (row.get("annotator_1_label") or "").strip()
            and (row.get("annotator_2_label") or "").strip()
            and (row.get("annotator_1_label") or "").strip() != (row.get("annotator_2_label") or "").strip()
            and adjudicated
        ):
            warnings.append(f"row {row_number}: annotators disagreed; retain the adjudication rationale in the controlled annotation log")

        if not source:
            if status == "approved_for_production":
                row_errors.append("approved_for_production requires a source_reference")
            else:
                warnings.append(f"row {row_number}: source_reference is missing; keep out of approval and training")
        if not permission or not permission.casefold().startswith("verified:"):
            if status == "approved_for_production":
                row_errors.append("approved_for_production requires verified permission and an evidence reference")
            else:
                warnings.append(f"row {row_number}: permission is missing or unresolved; keep out of approval and training")
        elif status == "approved_for_production" and not APPROVED_PERMISSION_PATTERN.fullmatch(permission):
            row_errors.append(
                "approved_for_production permission must use 'verified: <license/permission>; evidence: <URL or record:ID>'"
            )

        if row_errors:
            errors.extend(f"row {row_number}: {error}" for error in row_errors)

    return {"valid": not errors, "row_count": len(rows), "errors": errors, "warnings": warnings}


def validate_csv(path: Path) -> dict:
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            fieldnames = reader.fieldnames
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Could not read real campaign CSV: {path}") from exc
    report = validate_records(fieldnames, rows)
    report["input_path"] = str(Path(path).resolve())
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, nargs="?", default=TEMPLATE_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = validate_csv(args.csv_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
