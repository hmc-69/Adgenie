"""Generate a reproducible, explicitly synthetic pre-launch campaign dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "data"
GENERATOR_VERSION = "1.0.0"
DATASET_VERSION = "campaign-performance-synthetic-v1"
FEATURES = [
    "product_name",
    "description",
    "target_audience",
    "platform",
    "objective",
    "tone",
    "budget",
    "keywords",
]
TARGETS = {
    "ctr_percent": "Click-through rate percentage, generated directly as a bounded synthetic target.",
    "conversion_rate_percent": "Conversion percentage of clicks, generated directly as a bounded synthetic target.",
}

PLATFORMS = ["Instagram", "Facebook", "Google Ads", "LinkedIn"]
OBJECTIVES = ["Brand Awareness", "Product Promotion", "Lead Generation", "Website Traffic", "Sales"]
TONES = ["Professional", "Casual", "Friendly", "Exciting", "Persuasive"]
PRODUCTS = [
    "Wireless earbuds", "Fitness planner", "Reusable bottle", "Online design course",
    "Organic skincare set", "Project management software", "Travel backpack", "Coffee subscription",
    "Home gardening kit", "Accounting service", "Photography workshop", "Language learning app",
]
AUDIENCES = [
    "busy commuters seeking convenient everyday options",
    "small business owners comparing practical tools",
    "students looking for affordable learning resources",
    "fitness enthusiasts building consistent routines",
    "creative professionals exploring new workflows",
    "families planning useful purchases",
    "travelers preparing for short trips",
    "home cooks interested in simple ingredients",
    "new customers researching product features",
    "experienced buyers comparing quality and value",
]
DESCRIPTORS = [
    "introduces product features for daily use",
    "highlights a convenient service for a busy schedule",
    "explains the value of a guided learning experience",
    "presents a practical option for a common task",
    "shares a product update with useful details",
    "invites interested people to explore a new offer",
    "shows how the product fits into a familiar routine",
    "describes the service and its intended benefits",
    "focuses on product quality, design, and usability",
    "outlines a straightforward way to get started",
]
KEYWORD_SETS = [
    "new product; feature overview; everyday use",
    "local service; small business; lead inquiry",
    "learn online; guided course; skill building",
    "wellness; daily routine; practical choice",
    "travel gear; planning; product details",
    "home essentials; quality; simple setup",
    "special offer; product launch; explore more",
    "software tools; workflow; business use",
    "coffee subscription; delivery; customer choice",
    "creative workshop; practice; registration",
]


def _sigmoid(value: float) -> float:
    return 1 / (1 + np.exp(-value))


def generate_rows(rows: int = 5000, seed: int = 42) -> list[dict]:
    if rows < 100:
        raise ValueError("Generate at least 100 rows for a useful experiment.")
    rng = np.random.default_rng(seed)
    group_size = 5
    group_count = (rows + group_size - 1) // group_size
    group_shift = rng.normal(0, 0.18, size=group_count)
    records = []

    for index in range(rows):
        group_index = index // group_size
        platform = str(rng.choice(PLATFORMS, p=[0.30, 0.28, 0.27, 0.15]))
        objective = str(rng.choice(OBJECTIVES))
        tone = str(rng.choice(TONES))
        product = str(rng.choice(PRODUCTS))
        audience = str(rng.choice(AUDIENCES))
        descriptor = str(rng.choice(DESCRIPTORS))
        keywords = str(rng.choice(KEYWORD_SETS)) if rng.random() >= 0.12 else ""
        budget = float(np.exp(rng.uniform(np.log(50), np.log(30000)))) if rng.random() >= 0.10 else None

        platform_ctr = {"Instagram": 0.25, "Facebook": 0.05, "Google Ads": 0.48, "LinkedIn": -0.28}[platform]
        objective_ctr = {
            "Brand Awareness": 0.35, "Product Promotion": 0.10, "Lead Generation": 0.05,
            "Website Traffic": 0.40, "Sales": -0.12,
        }[objective]
        tone_ctr = {"Professional": -0.08, "Casual": 0.12, "Friendly": 0.18, "Exciting": 0.30, "Persuasive": 0.15}[tone]
        audience_ctr = 0.22 if any(word in audience for word in ("commuters", "travelers", "enthusiasts")) else -0.02
        budget_effect = 0.16 * np.log1p(budget or 0) / np.log1p(30000)
        brief_signal = 0.10 if any(word in descriptor for word in ("features", "product", "routine")) else -0.03
        ctr_logit = -3.45 + platform_ctr + objective_ctr + tone_ctr + audience_ctr + budget_effect + brief_signal
        ctr_logit += group_shift[group_index] + rng.normal(0, 0.38)
        ctr = float(np.clip(_sigmoid(ctr_logit) * 100, 0.05, 25.0))

        objective_cvr = {
            "Brand Awareness": -0.35, "Product Promotion": 0.15, "Lead Generation": 0.50,
            "Website Traffic": -0.05, "Sales": 0.58,
        }[objective]
        platform_cvr = {"Instagram": 0.10, "Facebook": 0.12, "Google Ads": 0.42, "LinkedIn": 0.20}[platform]
        audience_cvr = 0.34 if any(word in audience for word in ("comparing", "researching", "experienced")) else -0.08
        tone_cvr = {"Professional": 0.20, "Casual": -0.02, "Friendly": 0.14, "Exciting": -0.08, "Persuasive": 0.28}[tone]
        keyword_cvr = 0.15 if keywords else -0.10
        cvr_logit = -3.05 + objective_cvr + platform_cvr + audience_cvr + tone_cvr + keyword_cvr + 0.12 * budget_effect
        cvr_logit += group_shift[group_index] * 0.7 + rng.normal(0, 0.46)
        conversion_rate = float(np.clip(_sigmoid(cvr_logit) * 100, 0.05, 35.0))

        records.append({
            "scenario_group": f"scenario-{group_index:04d}",
            "product_name": product,
            "description": f"{product} {descriptor}",
            "target_audience": audience,
            "platform": platform,
            "objective": objective,
            "tone": tone,
            "budget": budget,
            "keywords": keywords,
            "ctr_percent": ctr,
            "conversion_rate_percent": conversion_rate,
        })

    return records


def generate_dataset(output_dir: Path = DEFAULT_OUTPUT, rows: int = 5000, seed: int = 42) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = generate_rows(rows=rows, seed=seed)
    dataset_path = output_dir / "campaign_performance_synthetic.csv"
    metadata_path = output_dir / "dataset_metadata.json"
    columns = ["scenario_group", *FEATURES, *TARGETS]
    with dataset_path.open("w", encoding="utf-8", newline="") as dataset_file:
        writer = csv.DictWriter(dataset_file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for record in records:
            normalized = dict(record)
            normalized["budget"] = "" if normalized["budget"] is None else f"{normalized['budget']:.8f}"
            normalized["ctr_percent"] = f"{normalized['ctr_percent']:.8f}"
            normalized["conversion_rate_percent"] = f"{normalized['conversion_rate_percent']:.8f}"
            writer.writerow(normalized)
    checksum = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    metadata = {
        "dataset_version": DATASET_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": seed,
        "row_count": len(records),
        "feature_count": len(FEATURES),
        "feature_columns": FEATURES,
        "feature_data_types": {name: ("number|null" if name == "budget" else "string") for name in FEATURES},
        "target_definitions": TARGETS,
        "target_units": {name: "percent" for name in TARGETS},
        "synthetic_data": True,
        "group_column": "scenario_group",
        "generation_assumptions": [
            "Rows describe simulated pre-launch campaign briefs, not real campaigns or users.",
            "Targets are directly simulated bounded rates using documented category effects, a shared scenario effect, and random noise.",
            "Conversion rate is a target rate, not conversions divided by fabricated clicks; zero-click observations are therefore not generated.",
            "Budget represents planned budget and is not actual spend.",
            "Duration and creative format are omitted because the application does not store them.",
            "The scenario group is used only to isolate related synthetic rows across data splits and is never a predictive feature.",
        ],
        "dataset_sha256": checksum,
        "generator_version": GENERATOR_VERSION,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return dataset_path, metadata_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    dataset_path, metadata_path = generate_dataset(args.output_dir, args.rows, args.seed)
    print(f"Generated {dataset_path}")
    print(f"Metadata: {metadata_path}")
    print(f"SHA-256: {hashlib.sha256(dataset_path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
