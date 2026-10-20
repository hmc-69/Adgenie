# Audience Analysis Annotation Guide

## Purpose and unit of annotation

Assign one label to the **dominant messaging-motivation archetype expressed by a complete campaign brief**. This is a classification of the brief's framing, not a claim about the real characteristics of people who see an ad. Read the product name, description, platform, objective, tone, and keywords together. Do not classify from product category alone.

Choose the motivation most explicitly supported by the brief. Do not infer protected or sensitive traits, demographics, purchasing behavior, or campaign performance. Do not turn a speculative audience description into evidence. If the brief does not support one specific label, or two or more motivations remain equally plausible, use `general_interest`.

Each example receives exactly one label from the approved set below. The examples are **synthetic annotation guidance only**. They are not real campaign records and must not be copied into the training dataset.

## Approved labels

### `convenience_seekers`

- **Definition:** The brief primarily emphasizes saving time, reducing effort, portability, simplicity, or making a routine easier.
- **Positive indicators:** “quick setup,” “one-step,” “easy to carry,” “simplify your routine,” or a clearly described convenience benefit.
- **Confusing cases:** Use `value_seekers` when affordability or cost is the main point. Use `quality_seekers` when dependable performance is emphasized more than ease. Do not use this label merely because the product is commonly convenient.
- **Synthetic guidance example:** “A compact charger that powers devices from one small travel kit, with a setup designed to take seconds.”

### `value_seekers`

- **Definition:** The brief primarily emphasizes affordability, cost savings, pricing, budget fit, or the amount offered for the price.
- **Positive indicators:** Explicit lower price, discounts, reduced operating costs, budget language, or a clearly stated value comparison.
- **Confusing cases:** Use `quality_seekers` if durability or performance is the central value proposition without an explicit price focus. Do not assume a product is affordable from its category or audience.
- **Synthetic guidance example:** “A home starter set that includes the listed essentials at one clearly stated introductory price.”

### `quality_seekers`

- **Definition:** The brief primarily emphasizes product quality, durability, reliability, precision, materials, or consistently strong performance.
- **Positive indicators:** Specific, supportable claims about construction, tested performance, reliability, or product standards.
- **Confusing cases:** Use `style_seekers` when appearance or design is the main appeal. Use `value_seekers` when price is central. Do not infer quality from a premium-sounding product name.
- **Synthetic guidance example:** “A tool made with specified corrosion-resistant materials and documented for repeated workshop use.”

### `style_seekers`

- **Definition:** The brief primarily emphasizes visual design, appearance, personal expression, aesthetics, or distinctive style.
- **Positive indicators:** Clear references to shape, color, finish, design choices, or visual presentation as the main benefit.
- **Confusing cases:** Use `quality_seekers` if materials or construction are the focus. Do not infer a customer's identity or preferences from an aesthetic description.
- **Synthetic guidance example:** “A desk lamp offered in a described sculptural form and coordinated color range for a considered workspace.”

### `learning_seekers`

- **Definition:** The brief primarily emphasizes learning, instruction, skill development, education, or gaining knowledge through the product or service.
- **Positive indicators:** Lessons, guided practice, tutorials, structured learning, or an explicit skill-building outcome.
- **Confusing cases:** Use `business_utility_seekers` when workplace efficiency is central and learning is incidental. Do not infer education level or age.
- **Synthetic guidance example:** “A language course with guided exercises and feedback focused on practicing conversation skills.”

### `business_utility_seekers`

- **Definition:** The brief primarily emphasizes a stated operational or professional use, such as managing a business workflow, serving clients, or supporting a work task.
- **Positive indicators:** Explicit business workflows, professional operations, team administration, or work-related outcomes.
- **Confusing cases:** Use `convenience_seekers` if the brief focuses on ease for general everyday use. Do not assign this label just because a product could be used at work.
- **Synthetic guidance example:** “An invoicing tool that organizes estimates and payment records for a small service business.”

### `hobby_interest_seekers`

- **Definition:** The brief primarily addresses participation in a clearly named recreational interest, craft, sport, or enthusiast activity.
- **Positive indicators:** The activity is explicitly named and central to the product use or campaign message.
- **Confusing cases:** Use `learning_seekers` when instruction or skill acquisition is the main benefit. Do not infer an activity from the product category alone.
- **Synthetic guidance example:** “A set of watercolor brushes described for detailed landscape painting and studio practice.”

### `gift_shoppers`

- **Definition:** The brief primarily frames the offer as a gift or helps select, prepare, or present a gift.
- **Positive indicators:** Explicit gift language, gifting occasions, gift packaging, or a stated gift-selection benefit.
- **Confusing cases:** Do not infer gifting from an attractive product or a seasonal date alone. Use another label if the brief's main message is a product benefit and gifting is incidental.
- **Synthetic guidance example:** “A boxed tea sampler presented as a ready-to-give host gift, with its included flavors listed.”

### `general_interest`

- **Definition:** The brief does not clearly support one of the eight specific motivations, or multiple motivations are equally plausible.
- **Positive indicators:** Broad product introduction, generic promotional copy, insufficient context, or equally strong competing motivations.
- **Confusing cases:** Do not use this label simply because the annotator is unfamiliar with a product; first review the full brief. Do use it rather than guessing when the text remains ambiguous.
- **Synthetic guidance example:** “A campaign introduces a new household product and names its category, but gives no specific benefit, use case, or motivation.”

## Annotation workflow

1. Confirm the example has a stable ID and a recorded source reference, license or permission, and privacy review. Do not accept a row for training until provenance is verified.
2. Read the entire brief and assign exactly one label in `annotator_1_label` or `annotator_2_label`. Annotators work independently and must not see each other's label before submitting where feasible.
3. If both annotations agree, record that label in `adjudicated_label` and `dominant_archetype`; mark `annotation_status` as `adjudicated` only after provenance and privacy checks also pass.
4. If annotations disagree, mark `annotation_status` as `adjudication_required`. A third reviewer applies the guide, documents the resolution in the project's controlled annotation log, and records the result in both final-label fields. Do not add undocumented free-form labels to the CSV.
5. Use `rejected` for examples with invalid provenance, unresolved ambiguity, unusable text, or privacy issues. Rejected examples are excluded from training.

## Agreement and distribution checks

- Before adjudication, report raw agreement and Cohen's kappa for the two independent annotators over examples both have labeled. Also inspect per-label disagreement; an overall score can hide weak agreement on a rare label.
- Review a confusion table of annotator labels and adjudication outcomes. Revisit definitions and retrain annotators if disagreements cluster around a label boundary.
- Before splitting, report counts and proportions for all nine final labels, including missing or rejected labels separately. Check class coverage across train, validation, and test splits after group-aware splitting.
- Record the agreement statistic, label counts, exclusions, and annotation-guide version in the dataset release notes. Do not treat agreement as evidence of predictive accuracy.

## Duplicate and near-duplicate handling

- Detect exact duplicates using normalized text hashes over the feature text.
- Review likely near-duplicates using product/campaign identifiers and text similarity. Mark related examples with a common `campaign_group_id`; do not count copied variants as independent evidence.
- Keep all exact or near-duplicate examples, campaigns from the same product family, and other strongly related material in one data split. Maintain any duplicate-cluster and split assignments in a versioned split manifest keyed by stable IDs; do not add unapproved columns to the CSV template.
- Retain or remove duplicate rows consistently and document the decision. Never split copies across train, validation, and test to inflate evaluation results.

## Prohibited label sources

Do not use Gemini-generated analysis, mock-provider output, model predictions, or synthetic examples as ground-truth labels. Labels must be assigned by human annotators using the complete, permitted campaign context and this guide.
