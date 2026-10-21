# Campaign performance prediction experiment

This module returns experimental estimates of campaign CTR and conversion rate from campaign setup fields that are present before launch: product name, description, target audience, platform, objective, tone, planned budget, and keywords. It does not read daily impressions, clicks, conversions, actual spend, revenue, or recorded analytics. Campaign duration and creative format are not stored by AdGenie and are not invented here.

## Synthetic data only

The generator creates simulated campaign briefs and bounded percentage targets using documented category effects plus scenario-level and row-level random noise. It creates no real users or campaigns. The CSV contains a scenario-group column for split isolation; that identifier is never a model feature. Conversion rate is generated directly as a target rate, not calculated from fabricated clicks. Planned budget remains separate from actual spend.

These assumptions make a reproducible pipeline demonstration possible, but they do not establish that the relationships hold in advertising. Held-out synthetic scores must not be described as real-world accuracy, and displayed estimates are not observed performance or guarantees.

## Generate and train

The core backend requirements do not include machine-learning packages. Use the isolated backend virtual environment and pinned experiment requirements:

```powershell
Set-Location .\backend
.\venv\Scripts\python.exe -m pip install -r .\datasets\campaign_performance_prediction\requirements-experimental.txt
.\venv\Scripts\python.exe .\datasets\campaign_performance_prediction\generate_dataset.py --rows 5000 --seed 42
.\venv\Scripts\python.exe .\datasets\campaign_performance_prediction\train_model.py --seed 42 --version campaign-performance-v3
```

The generator writes `data/campaign_performance_synthetic.csv` and `data/dataset_metadata.json`. For the same row count and seed, the CSV checksum is reproducible; generation timestamps in the metadata naturally differ. Metadata records feature and target definitions, row count, assumptions, seed, generator version, and SHA-256.

Training uses a fixed group-aware train/validation/test split. Related scenario groups cannot cross partitions. Numeric, categorical, and TF-IDF text preprocessing is fitted inside the saved pipelines using training data only. For each target independently, DummyRegressor, Linear Regression, and Random Forest are compared on validation MAE. The lowest validation MAE selects the pipeline; test MAE, RMSE, and R² are then calculated against the dummy baseline. A result is marked as a meaningful improvement only when test MAE is at least 5% lower than baseline test MAE. The test split is not used for model selection.

Artifacts are written to `backend/models/campaign_performance_prediction/<version>/`: the complete fitted pipelines, evaluation metrics, copied dataset metadata, and a manifest with dependency versions and file checksums. `active.json` names the active version and is updated after the artifact is written. Existing versions are never overwritten; choose a new `--version` for another training run.

The API reads this directory by default. To use a different trusted local artifact root (the directory containing `active.json`), set `CAMPAIGN_PERFORMANCE_MODEL_DIR`. The runtime verifies the active version, experiment designation, feature and target schema, Python and scikit-learn/joblib compatibility, and checksums before loading the locally generated joblib file. Missing or incompatible packages/artifacts return a controlled 503; the service does not create fallback predictions or retrain at startup.

## API and UI

After signing in, open an owned campaign and choose **Predict Performance** in the separate Campaign Performance Prediction section. The endpoint derives predictors from that campaign's saved setup; it accepts no copied client outcome fields and does not write a prediction history or daily performance record:

```text
POST /api/campaigns/{campaign_id}/performance/predict
Authorization: Bearer <the signed-in user's token>
```

The response includes `prediction_type: synthetic_experiment_only`, model version, bounded CTR and conversion-rate percentages, their units, selected-model and dummy-baseline test metrics, and explicit limitations. These predictions are displayed separately from the **Recorded performance** analytics section.

Prediction values are clipped to the valid percentage interval [0, 100] after checking they are finite. Clipping guarantees valid output ranges; it does not guarantee accuracy. MAE is average absolute error in percentage points, RMSE is the square root of average squared error in percentage points (which gives larger errors more weight), and R² compares error with a constant-mean predictor (1 is a perfect fit, 0 is no better than predicting the mean, and negative values are worse on that test split). Even favorable scores here describe only this synthetic generator.

To run checks from the repository root:

```powershell
Set-Location .\backend
.\venv\Scripts\python.exe -m unittest discover -s tests
Set-Location ..\frontend
npm test
npm run lint
npm run build
```

## What real validation would require

A real model would require authorized, timestamped campaign setup and outcomes from representative campaigns, consistent metric definitions, enough distinct campaigns across platforms/objectives, and a test set held out by campaign and preferably by time. It would also require evaluating drift, missingness, and performance against simple baselines before any operational use. Synthetic metrics in this module do not satisfy those requirements.
