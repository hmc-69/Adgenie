#!/usr/bin/env python3
"""Create deterministic, explicitly unvalidated synthetic audience-analysis drafts."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from random import Random
from typing import Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "campaign_briefs_template.csv"
REAL_TEMPLATE_PATH = SCRIPT_DIR / "real_campaign_briefs_template.csv"
DEFAULT_OUTPUT_PATH = SCRIPT_DIR / "synthetic_audience_drafts.csv"
PILOT_PATH = SCRIPT_DIR / "adgenie_audience_pilot_filled_template.csv"

CSV_COLUMNS = (
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
)

APPROVED_ARCHETYPES = (
    "convenience_seekers",
    "value_seekers",
    "quality_seekers",
    "style_seekers",
    "learning_seekers",
    "business_utility_seekers",
    "hobby_interest_seekers",
    "gift_shoppers",
    "general_interest",
)

SOURCE_REFERENCE = "Synthetic generated draft; no external source"
LICENSE_OR_PERMISSION = "Synthetic draft; not validated for production use"
SYNTHETIC_STATUS = "synthetic_ai_proposed_not_human_validated"
BOUNDARY_CASE_EVERY = 10

# Product groups describe related products/campaign families, independently of labels.
# The same product sequence is used across archetypes so related examples stay grouped.
PRODUCT_CONCEPTS = (
    ("FAM-HOME-01", "Countertop meal planner", ("organizing weekly recipes", "preparing a shopping list"), ("a reusable planning board", "a space for meal notes"), ("meal planning", "kitchen routine", "weekly menu")),
    ("FAM-HOME-02", "Adjustable reading lamp", ("setting up a reading corner", "lighting a focused desk area"), ("an adjustable arm", "a directional light head"), ("reading light", "desk setup", "adjustable lamp")),
    ("FAM-HOME-03", "Stackable storage baskets", ("sorting household supplies", "organizing a shared shelf"), ("a stackable shape", "open-front access"), ("home organization", "storage baskets", "shelf space")),
    ("FAM-HOME-04", "Pour-over coffee set", ("making coffee at home", "preparing a measured brew"), ("a dripper and serving carafe", "a measured brewing set"), ("coffee brewing", "home coffee", "pour over")),
    ("FAM-HOME-05", "Reusable food container set", ("packing meals for the day", "storing prepared ingredients"), ("nesting container sizes", "a coordinated lid set"), ("meal prep", "food storage", "reusable containers")),
    ("FAM-DIGITAL-01", "Shared appointment calendar", ("coordinating a week's appointments", "keeping a service schedule in view"), ("shared calendar access", "appointment reminders"), ("calendar", "scheduling", "reminders")),
    ("FAM-DIGITAL-02", "Personal reading app", ("organizing a digital reading list", "keeping notes beside saved articles"), ("bookmarks and reading notes", "a searchable saved list"), ("reading app", "digital notes", "saved articles")),
    ("FAM-DIGITAL-03", "Home energy dashboard", ("reviewing household energy use", "comparing daily usage summaries"), ("a usage overview", "time-based energy summaries"), ("energy dashboard", "home usage", "daily summary")),
    ("FAM-DIGITAL-04", "Photo organization software", ("sorting a growing photo library", "finding images from past projects"), ("tagged albums", "searchable collections"), ("photo library", "digital organization", "albums")),
    ("FAM-DIGITAL-05", "Language practice app", ("practicing short language exercises", "reviewing vocabulary in a daily session"), ("guided practice prompts", "a vocabulary review list"), ("language practice", "vocabulary", "guided exercises")),
    ("FAM-WORK-01", "Invoice tracking workspace", ("reviewing sent invoices", "organizing payment follow-ups"), ("an invoice status view", "a payment follow-up list"), ("invoices", "payment tracking", "business admin")),
    ("FAM-WORK-02", "Team project board", ("planning a shared project", "reviewing task ownership and dates"), ("a shared task board", "project milestones"), ("project board", "team tasks", "milestones")),
    ("FAM-WORK-03", "Small-shop inventory register", ("recording stock changes", "checking a product restock list"), ("stock level records", "a reorder overview"), ("inventory", "stock records", "retail operations")),
    ("FAM-WORK-04", "Client appointment portal", ("coordinating client appointments", "keeping service bookings organized"), ("a booking overview", "appointment status notes"), ("client bookings", "appointments", "service business")),
    ("FAM-WORK-05", "Document scanning station", ("organizing paper records", "preparing documents for a digital archive"), ("a scan-to-folder workflow", "searchable document files"), ("document scanning", "digital archive", "office workflow")),
    ("FAM-TRAVEL-01", "Carry-on packing organizer", ("packing a compact travel bag", "separating items for a weekend trip"), ("labeled packing compartments", "a fold-flat organizer"), ("travel packing", "carry on", "trip organizer")),
    ("FAM-TRAVEL-02", "Offline trip itinerary", ("keeping trip details together", "reviewing saved travel plans away from a connection"), ("an offline itinerary view", "saved booking notes"), ("travel itinerary", "offline access", "trip planning")),
    ("FAM-TRAVEL-03", "Insulated lunch carrier", ("bringing lunch on a commute", "carrying food for an outdoor day"), ("an insulated lining", "a separated container pocket"), ("lunch carrier", "commute", "outdoor day")),
    ("FAM-TRAVEL-04", "Compact charging kit", ("packing device chargers for a trip", "keeping cables together in a work bag"), ("a cable wrap", "a compact storage case"), ("charging kit", "travel accessories", "cable storage")),
    ("FAM-TRAVEL-05", "City walking guide", ("planning a self-guided city walk", "saving places for a neighborhood visit"), ("a route note collection", "a map-based place list"), ("city guide", "walking route", "saved places")),
    ("FAM-CREATIVE-01", "Watercolor starter palette", ("painting a small landscape study", "setting up a home art session"), ("a selection of mixing wells", "a compact color palette"), ("watercolor", "painting", "creative practice")),
    ("FAM-CREATIVE-02", "Beginner photography workbook", ("practicing camera composition", "learning to review exposure settings"), ("guided photo exercises", "step-by-step camera notes"), ("photography", "camera skills", "workbook")),
    ("FAM-CREATIVE-03", "Home baking tool kit", ("preparing a weekend baking project", "measuring ingredients for a bread recipe"), ("a dough scraper and measuring set", "a recipe planning card"), ("home baking", "bread making", "baking tools")),
    ("FAM-CREATIVE-04", "Model-building work mat", ("assembling a miniature model", "organizing parts for a craft session"), ("a marked work surface", "a parts tray"), ("model building", "craft supplies", "miniature models")),
    ("FAM-CREATIVE-05", "Digital music practice course", ("following a guided instrument practice", "reviewing music fundamentals"), ("short lesson sequences", "practice prompts and review notes"), ("music practice", "online course", "guided learning")),
    ("FAM-AUDIO-01", "Wireless listening headset", ("listening to audio during a commute", "joining a remote work call"), ("a foldable headband", "on-device listening controls"), ("headset", "wireless audio", "listening")),
    ("FAM-AUDIO-02", "Portable desktop speaker", ("playing audio in a study space", "setting up sound for a small gathering"), ("a compact speaker enclosure", "a simple desk connection"), ("desktop speaker", "home audio", "portable sound")),
    ("FAM-AUDIO-03", "Podcast recording microphone", ("recording a spoken tutorial", "setting up a small podcast session"), ("a desktop stand", "a direct monitoring control"), ("recording microphone", "podcast", "audio production")),
    ("FAM-AUDIO-04", "Vinyl record storage shelf", ("organizing a record collection", "displaying frequently played albums"), ("open album dividers", "a compact shelf layout"), ("record shelf", "vinyl collection", "music room")),
    ("FAM-AUDIO-05", "Children's story audio player", ("playing a recorded story at home", "choosing an audio story for a quiet activity"), ("physical story controls", "a set of recorded story cards"), ("audio stories", "story player", "listening")),
    ("FAM-OUTDOOR-01", "Trail daypack", ("packing supplies for a day hike", "carrying a water bottle and map outdoors"), ("a divided main compartment", "a stretch side pocket"), ("day hiking", "outdoor pack", "trail gear")),
    ("FAM-OUTDOOR-02", "Foldable picnic blanket", ("setting up a park picnic", "packing a ground cover for an outdoor event"), ("a foldable carry design", "a patterned top surface"), ("picnic", "park outing", "outdoor blanket")),
    ("FAM-OUTDOOR-03", "Home herb garden kit", ("growing herbs on a kitchen sill", "starting a small container garden"), ("seed packets and plant markers", "a compact growing tray"), ("herb garden", "container gardening", "planting")),
    ("FAM-OUTDOOR-04", "Reusable insulated bottle", ("carrying a drink during a walk", "keeping water nearby through the day"), ("a screw-top lid", "a carry loop"), ("reusable bottle", "walking", "hydration accessory")),
    ("FAM-OUTDOOR-05", "Compact bird-watching journal", ("noting birds seen on a local walk", "recording observations in a garden"), ("dated observation pages", "a species checklist section"), ("bird watching", "nature journal", "field notes")),
    ("FAM-GIFT-01", "Custom photo book service", ("arranging selected photos into a keepsake", "preparing a printed memory album"), ("captioned page layouts", "a choice of cover finishes"), ("photo book", "keepsake", "printed album")),
    ("FAM-GIFT-02", "Tea sampler box", ("choosing a host gift", "assembling a small thank-you present"), ("a range of tea varieties", "a ready-to-wrap box"), ("tea sampler", "host gift", "thank you gift")),
    ("FAM-GIFT-03", "Personalized stationery set", ("preparing a note-writing gift", "selecting stationery for a celebration"), ("a name-printed note card", "matching envelopes"), ("stationery", "personalized gift", "note cards")),
    ("FAM-GIFT-04", "Family recipe archive book", ("collecting recipes into a family book", "preparing a cooking keepsake"), ("recipe pages with prompts", "space for handwritten notes"), ("recipe book", "family keepsake", "cooking gift")),
    ("FAM-GIFT-05", "Desk plant presentation set", ("choosing a small desk present", "preparing a housewarming token"), ("a ceramic planter", "a care card and plant pot"), ("desk plant", "housewarming", "plant gift")),
)

CAMPAIGN_PLATFORMS = (
    "Instagram", "Facebook", "LinkedIn", "Google Ads", "YouTube", "TikTok", "Pinterest", "Reddit"
)
CAMPAIGN_OBJECTIVES = (
    "Brand Awareness", "Product Promotion", "Lead Generation", "Website Traffic", "Sales",
    "App Installs", "Demo Requests", "Event Registrations", "Newsletter Signups",
)
CAMPAIGN_TONES = (
    "Professional", "Friendly", "Playful", "Practical", "Informative", "Warm",
    "Confident", "Calm", "Direct", "Curious",
)

# Provisional message angles describe plausible campaign framing in ordinary language.
# They deliberately avoid label names, annotation language, and class-specific keywords.
MESSAGE_FRAMINGS = {
    "convenience_seekers": (
        "Keep the day's plan and the next step together in one place.",
        "Move from setup to the activity with fewer separate tasks.",
        "A compact arrangement leaves more room for the rest of the routine.",
        "Bring the key pieces along and have them ready when needed.",
        "Show how the small steps fit into one straightforward sequence.",
    ),
    "value_seekers": (
        "Set out the included items beside the listed price for an easy comparison.",
        "Place the available features beside the stated price and let the details speak.",
        "Make package contents clear before someone decides whether the offer fits their plans.",
        "Explain the available options without promising savings that have not been verified.",
        "Give a plain account of the items and services covered by the stated cost.",
    ),
    "quality_seekers": (
        "Bring the construction details into view and support claims with product evidence.",
        "Show the materials and finish clearly, using only specifications that can be verified.",
        "Explain how the described parts are assembled, without making unsupported comparisons.",
        "Let a close look at the components carry the story; confirm every performance claim.",
        "Use documented product details to explain what has gone into the finished item.",
    ),
    "style_seekers": (
        "Let the shape, color, and finish set the scene.",
        "Show the item in a composed setting where its visual details are easy to notice.",
        "Pair the product with complementary colors and a considered layout.",
        "Use a close view of the form and surface to guide the creative direction.",
        "Present the object as part of a carefully arranged space.",
    ),
    "learning_seekers": (
        "Break the process into a short demonstration with a useful takeaway.",
        "Explain one step at a time, then invite viewers to try the method themselves.",
        "Use a worked example to make the underlying idea easier to follow.",
        "Pair a clear explanation with a small practice activity.",
        "Turn the feature into a simple how-to, with terms explained as they appear.",
    ),
    "business_utility_seekers": (
        "Map the feature to a work task and show where it fits in the existing process.",
        "Walk through how a team could record the next action and its status.",
        "Show the handoff between routine steps without promising a business outcome.",
        "Connect the product view to a concrete service or operations task.",
        "Use a work scenario to explain how the information is organized.",
    ),
    "hobby_interest_seekers": (
        "Center the story on time spent practicing the named activity.",
        "Show the materials in use during a small project from start to finish.",
        "Build the creative around a familiar moment in the activity itself.",
        "Invite viewers to explore another technique for the pastime.",
        "Let the process and its details take focus in an activity-based scene.",
    ),
    "gift_shoppers": (
        "Show the item prepared for a host or as a thank-you gesture.",
        "Present the package as a thoughtful option for a celebration, if packaging supports it.",
        "Pair the product with a note and a ready-to-present arrangement.",
        "Help someone picture sharing the item with a friend or family member.",
        "Show the presentation details without assuming who will receive it.",
    ),
    "general_interest": (
        "Introduce the item and its use without centering one particular reason to choose it.",
        "Offer a broad overview of the product and the context where it may be used.",
        "Describe the main feature and let viewers decide which details matter to them.",
        "Give a balanced introduction without implying a particular need or preference.",
        "Show the product in context and keep the message open-ended.",
    ),
}

DESCRIPTION_OPENERS = (
    "With {product}, show {use_case}",
    "{product} appears in a scene about {use_case}",
    "{use_case_cap} provides context for {product}",
    "A visual featuring {product} during {use_case}",
    "Start with {detail} from {product}",
    "While {use_case}, bring {product} into view",
    "{detail_cap} gives {product} a scene for {use_case}",
    "Feature {product} as part of {use_case}",
    "A campaign scene places {product} near {detail}",
    "{product} takes focus during {use_case}",
    "For {use_case}, place {product} beside {detail}",
    "From {detail} to {product}, follow {use_case}",
    "A moment of {use_case} brings {product} into view",
    "Show {detail} while {use_case} with {product}",
    "{product} and {detail} appear during {use_case}",
    "Set {product} within a scene of {use_case}",
    "{use_case_cap}, with {product} and {detail} in frame",
    "Begin with {product}, then show {use_case}",
    "A scene for {use_case} features {product}",
    "Bring {detail} forward in a view of {product}",
    "{product} is the subject; {use_case} sets the context",
    "For a product story, show {product} during {use_case}",
    "{detail_cap} appears alongside {product} in {use_case}",
    "Consider {product} in the context of {use_case}",
)
DETAIL_LINES = (
    "The described feature is {detail}.",
    "The item includes {detail}.",
    "Bring {detail} into the shot.",
    "Its product details include {detail}.",
    "The offer describes {detail}.",
    "Keep {detail} visible in the scene.",
)


def validate_archetypes() -> None:
    if tuple(MESSAGE_FRAMINGS) != APPROVED_ARCHETYPES:
        raise ValueError("Synthetic content must define exactly the approved archetypes in their required order.")


def read_template_columns(template_path: Path = TEMPLATE_PATH) -> tuple[str, ...]:
    try:
        with template_path.open("r", newline="", encoding="utf-8-sig") as source:
            columns = tuple(next(csv.reader(source)))
    except (OSError, StopIteration, csv.Error) as exc:
        raise ValueError(f"Could not read the campaign brief template header: {template_path}") from exc
    if columns != CSV_COLUMNS:
        raise ValueError("The campaign brief template columns or column order do not match the required schema.")
    if Path(template_path).resolve() == TEMPLATE_PATH.resolve():
        try:
            with REAL_TEMPLATE_PATH.open("r", newline="", encoding="utf-8-sig") as source:
                real_columns = tuple(next(csv.reader(source)))
        except (OSError, StopIteration, csv.Error) as exc:
            raise ValueError(f"Could not read the real campaign brief template header: {REAL_TEMPLATE_PATH}") from exc
        if real_columns != CSV_COLUMNS:
            raise ValueError("The real campaign brief template does not match the exact 15-column schema.")
    return columns


def generate_drafts(examples_per_class: int = 100, seed: int = 42) -> list[dict[str, str]]:
    if examples_per_class < 1:
        raise ValueError("--examples-per-class must be at least 1.")
    validate_archetypes()
    read_template_columns()

    rng = Random(seed)
    rows: list[dict[str, str]] = []
    for example_index in range(examples_per_class):
        group_id, product_name, use_cases, details, base_keywords = PRODUCT_CONCEPTS[
            example_index % len(PRODUCT_CONCEPTS)
        ]
        use_case = rng.choice(use_cases)
        detail = rng.choice(details)
        for archetype in APPROVED_ARCHETYPES:
            framing = rng.choice(MESSAGE_FRAMINGS[archetype])
            # One in ten briefs intentionally combines two plausible angles.
            # The assigned field remains only a synthetic proposal for human review.
            if (example_index + 1) % BOUNDARY_CASE_EVERY == 0 and archetype != "general_interest":
                other_label = APPROVED_ARCHETYPES[(APPROVED_ARCHETYPES.index(archetype) + 1) % (len(APPROVED_ARCHETYPES) - 1)]
                framing = f"{framing} Alongside this, {rng.choice(MESSAGE_FRAMINGS[other_label])}"
            opener = rng.choice(DESCRIPTION_OPENERS).format(
                product=product_name,
                use_case=use_case,
                use_case_cap=use_case[:1].upper() + use_case[1:],
                detail=detail,
                detail_cap=detail[:1].upper() + detail[1:],
            )
            detail_line = rng.choice(DETAIL_LINES).format(detail=detail)
            description = f"{opener}. {detail_line} {framing}"
            contextual_keywords = rng.sample(("seasonal planning", "daily routine", "feature overview", "product details", "campaign story", "use case", "new release", "how it works"), 2)
            keywords = list(dict.fromkeys((*base_keywords, *contextual_keywords)))
            row = {
                "example_id": f"SYN-{seed}-{rng.getrandbits(64):016x}",
                "campaign_group_id": group_id,
                "product_name": product_name,
                "description": description,
                "platform": rng.choice(CAMPAIGN_PLATFORMS),
                "objective": rng.choice(CAMPAIGN_OBJECTIVES),
                "tone": rng.choice(CAMPAIGN_TONES),
                "keywords": "; ".join(keywords),
                # A proposed archetype only; annotation/adjudication remain blank.
                "dominant_archetype": archetype,
                "annotator_1_label": "",
                "annotator_2_label": "",
                "adjudicated_label": "",
                "source_reference": SOURCE_REFERENCE,
                "license_or_permission": LICENSE_OR_PERMISSION,
                "annotation_status": SYNTHETIC_STATUS,
            }
            rows.append(row)

    rng.shuffle(rows)
    validate_drafts(rows, examples_per_class)
    return rows


def validate_drafts(rows: Sequence[dict[str, str]], examples_per_class: int) -> None:
    validate_archetypes()
    columns = read_template_columns()
    if len(rows) != examples_per_class * len(APPROVED_ARCHETYPES):
        raise ValueError("Generated row count does not match examples-per-class and archetype count.")

    ids: list[str] = []
    counts: Counter[str] = Counter()
    required_fields = (
        "example_id", "campaign_group_id", "product_name", "description", "platform",
        "objective", "tone", "keywords", "dominant_archetype", "source_reference",
        "license_or_permission", "annotation_status",
    )
    for row in rows:
        if tuple(row.keys()) != columns:
            raise ValueError("A generated row does not match the exact template schema and order.")
        if any(not row[field].strip() for field in required_fields):
            raise ValueError("A generated row is missing a required field.")
        label = row["dominant_archetype"]
        if label not in APPROVED_ARCHETYPES:
            raise ValueError(f"Generated an unsupported archetype: {label}")
        if any(row[field] for field in ("annotator_1_label", "annotator_2_label", "adjudicated_label")):
            raise ValueError("Synthetic labels must not be represented as human annotations or adjudication.")
        if row["source_reference"] != SOURCE_REFERENCE:
            raise ValueError("Synthetic provenance marker is missing or unexpected.")
        if row["license_or_permission"] != LICENSE_OR_PERMISSION:
            raise ValueError("Synthetic permission marker is missing or unexpected.")
        if row["annotation_status"] != SYNTHETIC_STATUS:
            raise ValueError("Synthetic rows must use the explicit unvalidated annotation status.")
        if any(approved_label in row["campaign_group_id"] for approved_label in APPROVED_ARCHETYPES):
            raise ValueError("Campaign group IDs must describe product families, not archetypes.")
        ids.append(row["example_id"])
        counts[label] += 1

    if len(ids) != len(set(ids)):
        raise ValueError("Generated example IDs are not unique.")
    incorrect_counts = {
        label: counts.get(label, 0)
        for label in APPROVED_ARCHETYPES
        if counts.get(label, 0) != examples_per_class
    }
    if incorrect_counts:
        raise ValueError(f"Generated class counts do not match the requested count: {incorrect_counts}")


def _is_synthetic_draft_file(path: Path) -> bool:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
                return False
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error):
        return False
    return bool(rows) and all(
        row.get("annotation_status") == SYNTHETIC_STATUS
        and row.get("source_reference") == SOURCE_REFERENCE
        and row.get("license_or_permission") == LICENSE_OR_PERMISSION
        and not row.get("annotator_1_label")
        and not row.get("annotator_2_label")
        and not row.get("adjudicated_label")
        for row in rows
    )


def write_drafts(rows: Sequence[dict[str, str]], output_path: Path, overwrite: bool = False) -> None:
    output_path = Path(output_path).expanduser().resolve()
    protected_names = {TEMPLATE_PATH.name, REAL_TEMPLATE_PATH.name, PILOT_PATH.name}
    if output_path.name in protected_names:
        raise ValueError(f"Refusing to write to protected dataset file: {output_path.name}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists; pass --overwrite only for generated synthetic drafts: {output_path}")
    if output_path.exists() and not _is_synthetic_draft_file(output_path):
        raise ValueError(f"Refusing to overwrite a file that is not an unvalidated synthetic draft: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", newline="", encoding="utf-8", dir=output_path.parent, delete=False
            ) as target:
                temporary_path = Path(target.name)
                writer = csv.DictWriter(target, fieldnames=CSV_COLUMNS, extrasaction="raise")
                writer.writeheader()
                writer.writerows(rows)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary_path, output_path)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
        return

    file_descriptor: int | None = None
    created_by_this_run = False
    try:
        file_descriptor = os.open(output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
        created_by_this_run = True
        with os.fdopen(file_descriptor, "w", newline="", encoding="utf-8") as target:
            file_descriptor = None
            writer = csv.DictWriter(target, fieldnames=CSV_COLUMNS, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
    except Exception:
        if file_descriptor is not None:
            os.close(file_descriptor)
        if created_by_this_run and output_path.exists():
            output_path.unlink()
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output CSV path (default: synthetic_audience_drafts.csv in this directory).")
    parser.add_argument("--examples-per-class", type=int, default=200, help="Number of synthetic drafts per approved archetype (default: 200; 1,800 total).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible content variation (default: 42).")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing file only when it is recognized as an unvalidated synthetic draft.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        drafts = generate_drafts(args.examples_per_class, args.seed)
        write_drafts(drafts, args.output, overwrite=args.overwrite)
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {len(drafts)} synthetic, unvalidated drafts to {args.output.resolve()}")
    print(f"Examples per archetype: {args.examples_per_class}; seed: {args.seed}")
    print("Proposed dominant_archetype values are not human-validated labels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
