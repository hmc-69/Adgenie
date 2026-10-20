# Audience Analysis Dataset

## Purpose

This directory is for preparing a human-labeled dataset for a future supervised classifier of the **dominant messaging-motivation archetype expressed in a campaign brief**. It is not a dataset of verified audience demographics, behavior, purchases, or advertising performance.

The human annotation template, [`campaign_briefs_template.csv`](campaign_briefs_template.csv), is header-only. This directory also contains a separate 45-row pilot file, `adgenie_audience_pilot_filled_template.csv`; its rows are marked synthetic and its proposed labels are **not** verified ground truth. Follow [`ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md) before collecting or labeling real data.

## CSV data dictionary

| Column | Meaning | Role |
| --- | --- | --- |
| `example_id` | Stable unique identifier for this brief row. | Metadata / record key |
| `campaign_group_id` | Identifier grouping related examples from one campaign, product, or strongly related campaign family. Use it to prevent related examples crossing splits. | Metadata / split grouping |
| `product_name` | Product or service name from the authorized source. | Feature |
| `description` | Campaign/product description, with personal and confidential details removed. | Feature |
| `platform` | Campaign platform as recorded in the source; use the application's canonical value where applicable, such as `Instagram`, `Facebook`, `Google Ads`, or `LinkedIn`. | Feature |
| `objective` | Campaign objective as recorded in the source; use the application's canonical value where applicable, such as `Brand Awareness`, `Product Promotion`, `Lead Generation`, `Website Traffic`, or `Sales`. | Feature |
| `tone` | Campaign tone as recorded in the source; use the application's canonical value where applicable, such as `Professional`, `Casual`, `Friendly`, `Exciting`, or `Persuasive`. | Feature |
| `keywords` | Relevant campaign keywords. If multiple values are stored in one cell, separate them with semicolons; quote CSV cells containing commas or quotes using standard CSV escaping. | Feature |
| `dominant_archetype` | Final canonical training label. Populate only after adjudication and only with one of the nine approved labels. It must match `adjudicated_label` for accepted training rows. | Label / target |
| `annotator_1_label` | First independent human label, from the approved set. | Annotation metadata |
| `annotator_2_label` | Second independent human label, from the approved set. | Annotation metadata |
| `adjudicated_label` | Final human-reviewed label from the approved set. | Final label / target source |
| `source_reference` | Auditable internal source ID or controlled reference to the source record. Do not place credentials or sensitive personal information here. | Provenance metadata |
| `license_or_permission` | Recorded license name/reference or explicit authorization record sufficient to verify training use. Blank or unverified permission means the example is not accepted for training. | Provenance metadata |
| `annotation_status` | One of `pending`, `independently_annotated`, `adjudication_required`, `adjudicated`, or `rejected`. `adjudicated` is training-eligible only after provenance and privacy checks pass. | Workflow metadata |

The intended model features are `product_name`, `description`, `platform`, `objective`, `tone`, and `keywords`. The model target is the final adjudicated label in `adjudicated_label` (mirrored in `dominant_archetype` for a convenient finalized dataset export). IDs, annotator labels, provenance, and workflow status are metadata, not model features. Avoid including fields that reveal the answer directly without documenting and evaluating the resulting leakage risk.

## Approved target values

The only accepted label values are:

`convenience_seekers`, `value_seekers`, `quality_seekers`, `style_seekers`, `learning_seekers`, `business_utility_seekers`, `hobby_interest_seekers`, `gift_shoppers`, and `general_interest`.

These are text-motivation categories, not descriptions of actual people. Do not add labels ad hoc; update and version the annotation guide before changing the taxonomy.

## Collection, permission, and licensing

Before adding a row, record where it came from and verify that the applicable license or written authorization permits storing and using the text for machine-learning training. Check applicable terms and restrictions, attribution obligations, confidentiality commitments, and retention requirements. Keep evidence in an access-controlled provenance record referenced by `source_reference` or `license_or_permission`; do not rely on public availability alone as proof of training permission. Exclude examples if permission cannot be confirmed.

Remove names, email addresses, phone numbers, account IDs, customer records, unpublished pricing, confidential strategy, credentials, and other personal or confidential information before annotation. Preserve only the minimum text needed to represent the campaign brief. Restrict dataset access to authorized project personnel and follow the source's deletion and retention conditions.

## Class balance and split hygiene

Review both raw counts and proportions for all labels. A dominant class can make aggregate results look favorable while minority labels perform poorly. Collect diverse, genuinely distinct examples for underrepresented labels; do not manufacture balance by copying, oversampling, or duplicating minority examples before splitting. If resampling is later evaluated, apply it only to the training partition after the group-aware split.

Group exact and near-duplicate briefs, related campaign variants, and related product families. Keep each group in only one partition. Store split assignments in a versioned manifest keyed by `example_id`/`campaign_group_id`, and record the grouping and stratification method. Stratify by final label where counts permit, while respecting groups.

Reserve an untouched test set before model selection. Use training data to fit, validation data to choose settings and thresholds, and the test set once for final evaluation. Do not tune against test results or use them to revise labels without creating a new documented dataset/model evaluation release. Report the class distribution for each partition and per-class metrics; the test set is essential for estimating performance on held-out briefs.

## Synthetic examples

### Draft generator

`generate_synthetic_audience_drafts.py` creates a separate `synthetic_audience_drafts.csv`; it never writes to the human annotation template or pilot file. It uses local deterministic templates and a seeded pseudo-random generator, and makes no network or model/API calls.

From the repository root, generate the default 200 drafts per archetype (1,800 total):

```shell
python backend/datasets/audience_analysis/generate_synthetic_audience_drafts.py
```

Generate a small sample at a chosen path with an explicit seed:

```shell
python backend/datasets/audience_analysis/generate_synthetic_audience_drafts.py --examples-per-class 2 --seed 17 --output backend/datasets/audience_analysis/synthetic_audience_drafts_smoke.csv
```

The varied wording version in `synthetic_audience_drafts_v3.csv` was generated with the same schema and labels, using a larger set of sentence openings and detail lines. It remains synthetic, provisional, and unsuitable as ground truth. To recreate it without replacing any existing output, use:

```powershell
python backend/datasets/audience_analysis/generate_synthetic_audience_drafts.py --examples-per-class 200 --seed 42 --output backend/datasets/audience_analysis/synthetic_audience_drafts_v3_recreated.csv
```

Options are `--output PATH`, `--examples-per-class N` (default `200`), `--seed N` (default `42`), and `--overwrite`. The generator validates the approved archetype list, exact 15-column template header and column order, required fields, unique IDs, per-class counts, and synthetic provenance markers before writing. It uses product-family campaign groups shared across labels, varied local phrase patterns, and a small set of intentionally mixed-angle briefs for later human review. It refuses to replace an existing destination unless `--overwrite` is provided; even then, it only replaces a file recognized as an unvalidated synthetic draft. The template and pilot filenames are protected.

Every newly generated row has `source_reference` = `Synthetic generated draft; no external source`, `license_or_permission` = `Synthetic draft; not validated for production use`, and `annotation_status` = `synthetic_ai_proposed_not_human_validated`. The `dominant_archetype` value is a **provisional synthetic proposal**, never an adjudicated label. The human annotation fields (`annotator_1_label`, `annotator_2_label`, and `adjudicated_label`) remain blank. These rows are not independently labeled and are not ground truth. Product-family `campaign_group_id` values are assigned independently of archetype; each family occurs across labels and is kept together for future splits. Some briefs deliberately combine plausible message angles; all generated rows need human review. Existing generated CSVs are not updated by this documentation or by running tests. Previously generated files can retain the older `Synthetic draft; review before production use` marker; the standalone training guard accepts either marker but still requires explicit `--allow-synthetic-labels`.

Use generated drafts only for parser, schema, and explicitly synthetic pipeline smoke tests, with synthetic data kept separate from genuine labeled data. Do not train/evaluate a production model on them, report their labels as human annotations, or use their performance to make real-world claims. Keep them separate and explicitly marked as synthetic. Never mix them into the human-labeled training or evaluation data.

## Standalone experimental classifier pipeline

`train_audience_classifier.py` is an offline experiment and is not imported by FastAPI or production inference. It uses TF-IDF text features with Logistic Regression and compares the test results with `DummyClassifier(strategy="most_frequent")`. The fixed feature set is `product_name`, `description`, `platform`, `objective`, `tone`, and `keywords`, concatenated as text. IDs, `campaign_group_id`, source/license fields, annotation metadata, `adjudicated_label`, `dominant_archetype`, and `ad_target_audience` are excluded to reduce leakage. The default target is `dominant_archetype`; for an accepted human-labeled dataset, select `adjudicated_label` explicitly.

The default dataset is the synthetic draft CSV. Training on a dataset carrying the synthetic provenance markers is refused unless the user explicitly opts in. A synthetic smoke run (when scikit-learn and joblib are available) is:

```shell
python backend/datasets/audience_analysis/train_audience_classifier.py --dataset backend/datasets/audience_analysis/synthetic_audience_drafts.csv --target-column dominant_archetype --seed 42 --allow-synthetic-labels
```

For human-labeled data, use the adjudicated target and omit the synthetic opt-in:

```shell
python backend/datasets/audience_analysis/train_audience_classifier.py --dataset PATH_TO_APPROVED_DATASET.csv --target-column adjudicated_label --seed 42
```

The trainer reports both a seeded row-stratified holdout and a seeded group-aware stratified holdout on `campaign_group_id`. The group-aware split is primary; the row-level score is included only to show how a split that mixes related campaign families compares. The group splitter searches only group partitions for class coverage and a reasonable test fraction. It fails with an actionable error if classes cannot be represented on both sides; it never falls back to row-level splitting for the group-aware result. Both reports include accuracy, macro precision/recall/F1, per-class precision/recall/F1/support, confusion matrix, overall and split class counts, split sizes, and model parameters. Results are one holdout experiment, not a guarantee of generalization. Synthetic results must be labeled `synthetic_experiment_only` and interpreted only as pipeline smoke tests.

Artifacts and JSON reports are written below `backend/datasets/audience_analysis/experimental_output/`; existing run directories are not overwritten. The manifest records the dataset path and SHA-256, seed, feature and target columns, split method, class mapping, scikit-learn version, parameters, and experimental status. The model file is a trusted local joblib/pickle artifact: the script creates artifacts but never loads one. Do not load arbitrary joblib/pickle files, move these experimental artifacts into application code, or use them as production model releases.

Training requires scikit-learn and joblib. They are not part of the backend requirements and should be installed only in a separate experimental environment. The current pinned experiment set is in `requirements-experimental.txt`: scikit-learn 1.8.0 and joblib 1.6.0. Pandas is not used by the training script. The installed local CPython 3.14.5 AMD64 interpreter matches the official scikit-learn 1.8.0 Python requirement and published Windows x64 wheel. The backend runtime and `backend/requirements.txt` remain unchanged.

From the repository root, these PowerShell commands create and prepare the isolated environment, then run the offline tests without starting training:

```powershell
py -3.14 -m venv backend/datasets/audience_analysis/.venv
& backend/datasets/audience_analysis/.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/datasets/audience_analysis/requirements-experimental.txt
python -m unittest discover -s backend/datasets/audience_analysis -p "test_*.py" -v
```

In a later terminal session, activate it again before running tools:

```powershell
& backend/datasets/audience_analysis/.venv/Scripts/Activate.ps1
```

No pandas or production packages are needed. These tests do not call external services. A later training run on the current synthetic CSV must explicitly pass `--allow-synthetic-labels`; its metrics are smoke-test results only.

The existing `validate_audience_pilot.py` is a legacy validator and is not the generator's validation path. It currently contains a stray package-install command, an inconsistent CSV argument definition, and a pandas dependency; its strict pilot checks are fixed to the existing pilot's row/count assumptions. Do not run it as a general validator for generated drafts without first repairing and parameterizing it. The generator's validation is implemented with Python's standard library.

## Dataset release and readiness checklist

## Real-data discovery and annotation preparation

Real-data research and review are kept in four distinct stages:

1. **Synthetic draft data:** `synthetic_audience_drafts.csv` and the synthetic pilot are pipeline-only, unvalidated, and never ground truth.
2. **Unreviewed external data:** record potential sources in [`DATA_SOURCE_REGISTER.md`](DATA_SOURCE_REGISTER.md). Do not download/import automatically. Public availability does not establish ML-training permission.
3. **Human-reviewed, permission-checked examples:** collect only minimal campaign text with verified source provenance and documented permission. Start with the blank [`real_campaign_briefs_template.csv`](real_campaign_briefs_template.csv) and follow [`REAL_DATA_ANNOTATION_GUIDE.md`](REAL_DATA_ANNOTATION_GUIDE.md). Keep unresolved source or permission records pending; do not approve them for production.
4. **Final adjudicated data:** only human-adjudicated records with permission evidence, privacy review, and matching `dominant_archetype` / `adjudicated_label` can be considered for a versioned model-development release.

The source assessment utility reads a local CSV and emits quality indicators without modifying the input. It counts exact descriptions after Unicode normalization, case-folding, and punctuation/whitespace normalization. Near duplicates use token-set Jaccard similarity at 0.85 and exclude exact normalized strings; the assessor reports CSV row-number pairs for manual review. Repeated prefixes are a separate statistic: the number of distinct six-token description prefixes occurring more than once. Two unrelated briefs may share a prefix, so this count is not an exact- or near-duplicate count. With `--label-column` and `--group-column`, the assessor also reports per-class counts/imbalance, class distribution over groups, missing and invalid labels, provenance/status counts, possible label-linked terms, and whether each class occurs in at least two groups. Near-duplicate and leakage reports are heuristics for review; they do not prove or rule out leakage. The group check is an initial feasibility signal, not a guarantee that a chosen stratified split will work. The tool does not certify source rights, automatically label examples, or train a model. From the repository root, activate the isolated experiment environment and run these PowerShell commands:

```powershell
& backend/datasets/audience_analysis/.venv/Scripts/Activate.ps1
python backend/datasets/audience_analysis/assess_audience_dataset.py PATH_TO_LOCAL.csv
python backend/datasets/audience_analysis/assess_audience_dataset.py PATH_TO_LOCAL.csv --label-column candidate_label --group-column campaign_id --output assessment_report.json
python backend/datasets/audience_analysis/validate_real_campaign_briefs.py
python backend/datasets/audience_analysis/validate_real_campaign_briefs.py PATH_TO_REAL_CAMPAIGN_BRIEFS.csv
python -m unittest discover -s backend/datasets/audience_analysis -p "test_real_audience_data_workflow.py" -v
```

The assessor checks dimensions, columns, missingness, duplicates, candidate field cardinalities, selected label values, likely identifiers/sensitive columns, outcome/leakage fields, and group availability. Privacy and outcome-field detection are heuristic, so manually review the source and text. The real-data validator rejects synthetic provenance, invalid labels, and conflicts between adjudicated and final label fields. Missing provenance or unresolved permission generates warnings while a record remains pending; `approved_for_production` is rejected unless source reference, adjudication, and a formatted permission-evidence reference are present. This is a recordkeeping gate, not legal advice or automated license verification.

Neither utility imports into the database or changes application behavior. Keep assessment reports separate from input data and avoid including raw personal text in reports or logs.

Before a dataset release is used for training, confirm:

- [ ] Every accepted row has a stable ID, source reference, and verified license or authorization for training.
- [ ] Personal and confidential information has been removed and privacy review is recorded.
- [ ] Every accepted row has exactly one final label from the approved nine-label set; `dominant_archetype` matches `adjudicated_label`.
- [ ] Independent annotation and disagreement adjudication are recorded where feasible; raw agreement and Cohen's kappa are reported.
- [ ] Label counts, proportions, rejected rows, missing values, and class coverage have been reviewed.
- [ ] Exact and near-duplicate handling is documented, and related examples are grouped into only one split.
- [ ] Train, validation, and untouched test assignments and methodology are versioned and reproducible.
- [ ] No Gemini outputs, mock outputs, model predictions, or synthetic examples are represented as human ground-truth labels.
- [ ] The data release, annotation-guide version, preprocessing, and evaluation report can be reproduced from documented inputs.

There is no fixed row-count threshold that guarantees a useful model. Feasibility depends on class distribution, source and product diversity, label clarity and annotator agreement, group-aware held-out coverage, and measured performance on a separate test set. If those checks are inadequate, collect or annotate more authorized data rather than claiming model readiness.
