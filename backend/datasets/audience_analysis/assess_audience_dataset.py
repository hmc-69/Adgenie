#!/usr/bin/env python3
"""Read-only quality and suitability assessment for a local campaign CSV."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Sequence


APPROVED_ARCHETYPES = frozenset({
    "convenience_seekers", "value_seekers", "quality_seekers", "style_seekers",
    "learning_seekers", "business_utility_seekers", "hobby_interest_seekers",
    "gift_shoppers", "general_interest",
})
TEXT_NAME_HINTS = ("text", "description", "brief", "copy", "caption", "creative", "headline", "title", "body", "message", "content")
ID_NAME_HINTS = ("_id", "id_", "identifier", "email", "phone", "account", "user", "customer", "advertiser", "page_name")
SENSITIVE_NAME_HINTS = ("email", "phone", "address", "ssn", "social_security", "birth", "dob", "age", "gender", "sex", "race", "ethnicity", "religion", "health", "medical", "sexual_orientation", "first_name", "last_name", "full_name", "person_name")
OUTCOME_NAME_HINTS = ("click", "conversion", "purchase", "sales", "revenue", "spend", "impression", "ctr", "roi", "performance", "outcome", "engagement", "lead_count", "result", "visit", "profit")
LIKELY_GROUP_COLUMNS = ("campaign_group_id", "campaign_id", "campaign_name", "campaign_group", "campaign_family")
PERSONAL_VALUE_PATTERNS = {
    "email_like": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    "phone_like": re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)"),
}


def _blank(value: object) -> bool:
    return value is None or not str(value).strip()


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[\w]+", normalized, flags=re.UNICODE))


def _near_duplicate_report(rows: list[dict[str, str | None]], column: str, threshold: float = 0.85) -> dict:
    """Find likely near-duplicate descriptions by token-set Jaccard similarity.

    This is a review heuristic, not semantic duplicate detection. It returns row
    indexes rather than reproducing campaign text in the report.
    """
    normalized_values: list[str] = []
    token_sets: list[set[str]] = []
    for row in rows:
        text = _normalized_text(str(row.get(column) or ""))
        normalized_values.append(text)
        token_sets.append(set(text.split()) if text else set())
    pairs: list[list[int]] = []
    for left, right in itertools.combinations(range(len(rows)), 2):
        a, b = token_sets[left], token_sets[right]
        if not a or not b:
            continue
        # Exact normalized strings are reported separately. Equal token sets
        # with different word order are still near duplicates and must remain.
        if normalized_values[left] == normalized_values[right]:
            continue
        if min(len(a), len(b)) / max(len(a), len(b)) < threshold:
            continue
        similarity = len(a & b) / len(a | b)
        if similarity >= threshold:
            pairs.append([left + 2, right + 2])
    return {"column": column, "method": "token-set Jaccard", "threshold": threshold, "pair_count": len(pairs), "csv_row_pairs": pairs[:100], "pairs_truncated": len(pairs) > 100}


def _leakage_report(rows: list[dict[str, str | None]], label_column: str, text_columns: list[str]) -> dict:
    stop_words = {"the", "a", "an", "and", "or", "to", "of", "in", "for", "with", "on", "by", "is", "are", "this", "that", "it", "as", "from", "at", "be", "can", "could", "may", "their", "its", "your", "one", "into"}
    label_rows: dict[str, list[dict[str, str | None]]] = {}
    for row in rows:
        label = str(row.get(label_column) or "").strip()
        if label:
            label_rows.setdefault(label, []).append(row)
    documents_by_label: dict[str, Counter[str]] = {}
    for label, label_examples in label_rows.items():
        docs = Counter()
        for row in label_examples:
            words = set(_normalized_text(" ".join(str(row.get(col) or "") for col in text_columns)).split()) - stop_words
            docs.update(words)
        documents_by_label[label] = docs
    distinctive = []
    total_docs = sum(len(v) for v in label_rows.values())
    for label, label_examples in label_rows.items():
        n = len(label_examples)
        for token, count in documents_by_label[label].items():
            in_rate = count / n
            other_n = total_docs - n
            other_count = sum(docs[token] for other, docs in documents_by_label.items() if other != label)
            other_rate = other_count / other_n if other_n else 0
            if n >= 2 and in_rate >= 0.5 and other_rate <= 0.05:
                distinctive.append({"token": token, "most_associated_label": label, "within_class_document_rate": round(in_rate, 4), "other_class_document_rate": round(other_rate, 4)})
    distinctive.sort(key=lambda item: (-item["within_class_document_rate"], item["token"]))

    prefix_counts = Counter()
    for row in rows:
        description = _normalized_text(str(row.get("description") or ""))
        prefix = " ".join(description.split()[:6])
        if prefix:
            prefix_counts[prefix] += 1
    repeated_prefixes = sorted((count for count in prefix_counts.values() if count > 1), reverse=True)
    return {
        "method": "document-frequency heuristic over selected text fields; review flagged terms and repeated six-token prefixes",
        "distinctive_label_linked_terms": distinctive[:100],
        "distinctive_term_count": len(distinctive),
        "repeated_description_prefix_count": len(repeated_prefixes),
        "largest_repeated_prefix_group_size": max(repeated_prefixes, default=0),
    }


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str | None]]]:
    try:
        with Path(path).open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise ValueError("CSV is empty or has no header row.")
            if any(not name for name in reader.fieldnames):
                raise ValueError("CSV has an empty column name.")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("CSV has duplicate column names.")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Could not read CSV: {path}") from exc
    return list(reader.fieldnames), rows


def analyze_csv(path: Path, label_column: str | None = None, group_column: str | None = None) -> dict:
    """Read a local CSV and return aggregate diagnostics without changing it."""
    path = Path(path)
    columns, rows = _read_csv(path)
    column_set = set(columns)
    candidate_text_columns = [
        column for column in columns
        if any(hint in column.casefold() for hint in TEXT_NAME_HINTS)
        and any(not _blank(row.get(column)) for row in rows)
    ]
    if not candidate_text_columns:
        candidate_text_columns = [
            column for column in columns
            if any(not _blank(row.get(column)) and len(str(row.get(column)).strip()) > 80 for row in rows)
        ]

    missing_counts = {
        column: sum(_blank(row.get(column)) for row in rows)
        for column in columns
    }
    missing_rates = {
        column: (missing_counts[column] / len(rows) if rows else 0.0)
        for column in columns
    }

    normalized_rows = [tuple(_normalized_text(str(row.get(column) or "")) for column in columns) for row in rows]
    seen_rows: set[tuple[str, ...]] = set()
    duplicate_rows = 0
    for signature in normalized_rows:
        if signature in seen_rows:
            duplicate_rows += 1
        else:
            seen_rows.add(signature)

    duplicate_briefs = 0
    if candidate_text_columns:
        seen_briefs: set[str] = set()
        for row in rows:
            signature = _normalized_text(" ".join(str(row.get(column) or "") for column in candidate_text_columns))
            if not signature:
                continue
            if signature in seen_briefs:
                duplicate_briefs += 1
            else:
                seen_briefs.add(signature)

    id_columns = [
        column for column in columns
        if any(hint in column.casefold() for hint in ID_NAME_HINTS)
    ]
    sensitive_columns = [
        column for column in columns
        if any(hint in column.casefold() for hint in SENSITIVE_NAME_HINTS)
    ]
    personal_value_signals = {
        column: {
            signal: sum(bool(pattern.search(str(row.get(column) or ""))) for row in rows)
            for signal, pattern in PERSONAL_VALUE_PATTERNS.items()
            if any(pattern.search(str(row.get(column) or "")) for row in rows)
        }
        for column in columns
    }
    personal_value_signals = {column: signals for column, signals in personal_value_signals.items() if signals}

    outcome_columns = [
        column for column in columns
        if any(hint in column.casefold() for hint in OUTCOME_NAME_HINTS)
    ]
    label_report = None
    if label_column:
        if label_column not in column_set:
            raise ValueError(f"Selected label column {label_column!r} is not present in the CSV.")
        counts = Counter(str(row.get(label_column) or "").strip() for row in rows)
        counts.pop("", None)
        invalid = {label: count for label, count in sorted(counts.items()) if label not in APPROVED_ARCHETYPES}
        label_report = {
            "column": label_column,
            "class_counts": dict(sorted(counts.items())),
            "missing_count": missing_counts[label_column],
            "labels_match_approved_archetypes": bool(rows) and not invalid and missing_counts[label_column] == 0,
            "invalid_labels": invalid,
            "class_imbalance": {
                "largest_to_smallest_ratio": (max(counts.values()) / min(counts.values())) if counts and min(counts.values()) else None,
                "represented_class_count": len(counts),
            },
        }

    selected_group = group_column or next((name for name in LIKELY_GROUP_COLUMNS if name in column_set), None)
    group_report = {"column": selected_group, "can_establish_groups": False}
    if selected_group:
        if selected_group not in column_set:
            raise ValueError(f"Selected group column {selected_group!r} is not present in the CSV.")
        group_values = [str(row.get(selected_group) or "").strip() for row in rows]
        nonempty_values = [value for value in group_values if value]
        counts = Counter(nonempty_values)
        group_report = {
            "column": selected_group,
            "can_establish_groups": bool(rows) and len(nonempty_values) == len(rows) and len(counts) >= 2,
            "unique_group_count": len(counts),
            "missing_rows": len(rows) - len(nonempty_values),
            "single_record_group_count": sum(count == 1 for count in counts.values()),
        }

    provenance_columns = [name for name in ("source_reference", "license_or_permission", "annotation_status") if name in column_set]
    provenance_counts = {
        column: dict(sorted(Counter(str(row.get(column) or "<missing>").strip() or "<missing>" for row in rows).items()))
        for column in provenance_columns
    }
    description_column = "description" if "description" in column_set else next((col for col in candidate_text_columns if "description" in col.casefold()), None)
    description_duplicates = 0
    near_duplicates = None
    if description_column:
        normalized_descriptions = [_normalized_text(str(row.get(description_column) or "")) for row in rows]
        nonempty_descriptions = [value for value in normalized_descriptions if value]
        description_duplicates = len(nonempty_descriptions) - len(set(nonempty_descriptions))
        near_duplicates = _near_duplicate_report(rows, description_column)

    class_group_report = None
    if label_column and selected_group:
        by_class: dict[str, Counter[str]] = {}
        for row in rows:
            label = str(row.get(label_column) or "").strip()
            group = str(row.get(selected_group) or "").strip()
            if label and group:
                by_class.setdefault(label, Counter())[group] += 1
        class_group_report = {
            label: {
                "row_count": sum(group_counts.values()),
                "distinct_group_count": len(group_counts),
                "group_size_distribution": dict(sorted(Counter(group_counts.values()).items())),
                "largest_group_size": max(group_counts.values(), default=0),
            }
            for label, group_counts in sorted(by_class.items())
        }
        group_report["class_distribution"] = class_group_report
        group_report["each_class_in_at_least_two_groups"] = bool(by_class) and all(len(counts) >= 2 for counts in by_class.values())
        group_report["potential_group_split_feasible"] = bool(group_report.get("can_establish_groups") and group_report["each_class_in_at_least_two_groups"] and len(by_class) >= 2)

    leakage_report = _leakage_report(rows, label_column, candidate_text_columns) if label_column else None

    warnings = []
    if not candidate_text_columns:
        warnings.append("No likely campaign text columns were identified by column name or text length.")
    if duplicate_rows:
        warnings.append(f"Found {duplicate_rows} exact normalized duplicate row(s). Review before splitting.")
    if duplicate_briefs:
        warnings.append(f"Found {duplicate_briefs} likely duplicate campaign brief(s) based on candidate text fields.")
    if description_duplicates:
        warnings.append(f"Found {description_duplicates} exact normalized duplicate description(s).")
    if near_duplicates and near_duplicates["pair_count"]:
        warnings.append(f"Found {near_duplicates['pair_count']} possible near-duplicate description pair(s); manually review the heuristic matches.")
    if id_columns or sensitive_columns or personal_value_signals:
        warnings.append("Potential identifiers or personal/sensitive data require privacy review; values are not included in this report.")
    if outcome_columns:
        warnings.append("Potential post-campaign outcomes/performance fields may leak information and should not be model features.")
    if not group_report.get("can_establish_groups"):
        warnings.append("Campaign grouping is absent or incomplete; a leakage-resistant grouped split cannot yet be established.")
    if label_report and not label_report["labels_match_approved_archetypes"]:
        warnings.append("Selected label column contains missing or non-approved archetype values.")
    if group_column and class_group_report and not group_report.get("potential_group_split_feasible"):
        warnings.append("At least one class is concentrated in fewer than two groups; group-aware class coverage may be infeasible.")
    if leakage_report and (leakage_report["distinctive_term_count"] or leakage_report["repeated_description_prefix_count"]):
        warnings.append("Potential label-linked wording or repeated description templates were detected; inspect before model evaluation.")

    return {
        "input_path": str(path.resolve()),
        "row_count": len(rows),
        "column_count": len(columns),
        "column_names": columns,
        "likely_text_fields": candidate_text_columns,
        "missing_values": {
            "counts": missing_counts,
            "rates": missing_rates,
        },
        "duplicate_rows": duplicate_rows,
        "likely_duplicate_campaign_briefs": duplicate_briefs,
        "description_duplicate_count": description_duplicates,
        "near_duplicate_descriptions": near_duplicates,
        "unique_value_counts": {column: len({str(row.get(column) or "") for row in rows if not _blank(row.get(column))}) for column in columns},
        "candidate_label_report": label_report,
        "potential_label_leakage": leakage_report,
        "provenance_and_status_counts": provenance_counts,
        "potential_identifier_columns": id_columns,
        "potential_sensitive_columns": sensitive_columns,
        "potential_personal_value_signals": personal_value_signals,
        "potential_target_leakage_or_post_campaign_fields": outcome_columns,
        "campaign_grouping": group_report,
        "warnings": warnings,
        "permission_notice": "Availability or downloadability does not establish permission to store or use data for ML training; review source terms and record evidence separately.",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--label-column", help="Optional candidate label column to count and validate.")
    parser.add_argument("--group-column", help="Optional campaign-group column to assess for split isolation.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path; input CSV remains read-only.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = analyze_csv(args.csv_path, args.label_column, args.group_column)
        rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            if Path(args.output).resolve() == Path(args.csv_path).resolve():
                raise ValueError("Report output path must not be the same as the input CSV path.")
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
