# Real Campaign Brief Annotation Guide

## Scope and separation

This workflow is for real campaign examples whose source and permission have been documented. It is separate from `campaign_briefs_template.csv`, the synthetic pilot, and `synthetic_audience_drafts.csv`. Do not copy any synthetic examples into `real_campaign_briefs_template.csv` or a real-data collection. The real template is header-only and has the same 15-column schema and order as the existing template.

The classification target is the dominant messaging motivation expressed by the campaign brief. A campaign's intended audience is not evidence of how its customers behave. Do not infer or record actual demographics, protected or sensitive traits, purchases, or ad performance from the brief.

## Before collecting a source

1. Record the official source, publisher, exact source/version, retrieval date, and stable record reference in a controlled provenance log.
2. Review the dataset license, source terms, API/platform terms, privacy terms, and any contractual restrictions. Public availability or API access is not permission for training, redistribution, or long-term storage.
3. Record evidence of permission in an access-controlled document or stable official license/terms reference. In the CSV, use `license_or_permission` in the form `verified: <license or written permission>; evidence: <URL or record:ID>` only after a human has reviewed the evidence. The validator checks the presence and format of that evidence reference; it does not make a legal determination.
4. Remove direct identifiers, customer records, personal contact details, sensitive personal information, and confidential or restricted campaign details. Keep only the minimum campaign context needed to annotate.
5. Assign a stable `example_id`. Use `campaign_group_id` for examples from the same campaign, campaign family, or near-duplicate creative family. If grouping cannot be established, keep the field blank and record a warning; such rows cannot be used in a leakage-resistant grouped split until resolved.

Do not automatically download or import a source. Assess a local file with `assess_audience_dataset.py`, review its source terms separately, and manually move only authorized, privacy-reviewed, relevant records into the real-data workflow.

## Annotation procedure

Use exactly one dominant archetype from the project's approved nine-label set in [`ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md). Read the full brief and campaign context. Do not assign a label from product category alone.

- Two annotators should independently fill `annotator_1_label` and `annotator_2_label` where feasible. They should work independently before comparing labels.
- Record the final human decision only in `adjudicated_label`. Keep the original annotator values intact. Never copy either annotation into the adjudicated column automatically.
- Populate `dominant_archetype` only after adjudication, and make it exactly match `adjudicated_label`. The real-data validator rejects a dominant label without an adjudicated label or mismatched final labels.
- If the brief does not support a dominant motivation, or multiple motivations remain equally plausible, leave all label fields blank and set `annotation_status` to `review_required`. Do not force `general_interest` when the correct action is unresolved review.
- Any label proposed by Gemini, another model, keyword rules, or the experimental synthetic classifier is only a proposal. Store such a proposal outside the label columns or in a separately controlled review log. A human must independently review the full brief before labeling; model output is never ground truth.
- For disagreements, set `adjudication_required`, then document the third-reviewer decision and rationale in the controlled annotation log before recording the final fields and setting `adjudicated`.

## Status values

Use one of these `annotation_status` values:

| Status | Meaning |
| --- | --- |
| `source_review_pending` | Source identity/relevance still needs review. |
| `permission_review_pending` | Training/storage permission has not been verified. |
| `annotation_pending` | Provenance may be recorded, but human annotation is not complete. |
| `independently_annotated` | Independent human labels have been collected; final adjudication is pending. |
| `adjudication_required` | Human annotators disagree or need a reviewer decision. |
| `review_required` | The brief is ambiguous, incomplete, or unsuitable for forced assignment; labels should remain blank until resolved. |
| `adjudicated` | A human final label is recorded. This alone does not prove permission or production eligibility. |
| `approved_for_production` | A human has confirmed relevance, privacy review, adjudication, source reference, and permission evidence. |
| `rejected` | Exclude the record because of provenance, permission, privacy, relevance, or quality concerns. |

`approved_for_production` requires a non-empty `source_reference`, a final adjudicated label matching `dominant_archetype`, and a `license_or_permission` value formatted as `verified: <license/permission>; evidence: <URL or record:ID>`. This is a documentation gate, not an automated legal review. Unresolved permission must remain pending and is not eligible for training.

## Exact CSV schema and field use

The CSV header and column order must remain:

```text
example_id,campaign_group_id,product_name,description,platform,objective,tone,keywords,dominant_archetype,annotator_1_label,annotator_2_label,adjudicated_label,source_reference,license_or_permission,annotation_status
```

Only `product_name`, `description`, `platform`, `objective`, `tone`, and `keywords` are potential model features. IDs, source references, permission evidence, annotator labels, adjudicated labels, and status are metadata/labels and must not be model features. The label taxonomy is exactly the nine values documented in `ANNOTATION_GUIDE.md`.

## Validation workflow

Run the validator before treating a CSV as part of the real-data workflow:

```powershell
python backend/datasets/audience_analysis/validate_real_campaign_briefs.py
python backend/datasets/audience_analysis/validate_real_campaign_briefs.py PATH_TO_REAL_CAMPAIGN_BRIEFS.csv
```

It checks the exact header, synthetic provenance markers, label values, duplicate IDs, adjudication consistency, approved-record provenance gates, and unresolved source/permission warnings. It does not certify licensing, privacy, annotation correctness, or model suitability. It does not import rows into the application or database.

## Privacy, grouping, and release

Never collect customer-level personal data or sensitive personal attributes. Review text values as well as column names; the assessment tool's pattern checks are heuristic and are not a privacy guarantee. Do not use reached-audience demographics or sensitive-trait targeting fields as features or labels.

Review duplicate briefs and group related records before splitting. A group-aware train/test split must keep a campaign and its near duplicates together. An unresolved group field is a blocker to leakage-resistant evaluation, not a reason to fall back to random row splitting.

Only human-reviewed, permission-checked, adjudicated examples may enter a real model-development release. Keep unreviewed external data, synthetic drafts, rejected rows, and the final adjudicated dataset in separate files/directories with distinct provenance. Never describe synthetic-run results as evidence about real campaigns or real audience behavior.
