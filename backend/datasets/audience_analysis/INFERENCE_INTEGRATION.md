# Experimental audience classifier inference

The backend audience-analysis endpoint attaches the `result.model_prediction` object by default. Set `AUDIENCE_CLASSIFIER_ENABLED=false` only to disable this experimental feature. Prediction is performed by the local TF-IDF + Logistic Regression artifact at:

backend/datasets/audience_analysis/experimental_output/synthetic-run-20261020T145421Z-seed-42/tfidf_logistic_regression.joblib

The loader accepts only that fixed group-aware artifact. It validates manifest status, target, feature list, classes, split metadata, source dataset hash, Python major/minor, exact scikit-learn/joblib versions, and a pinned SHA-256 for the model binary. It never loads a user-supplied path and does not fall back to Gemini or the mock provider for the prediction. With the feature enabled, a missing or incompatible artifact produces HTTP 503 before the narrative provider is called.

The existing provider still creates the audience overview, segments, targeting and messaging recommendations. The classifier prediction is kept in a separate optional field and does not determine or rewrite those recommendations. Existing frontend clients can ignore this additive field. The history endpoint computes predictions for older saved analyses from their stored campaign snapshots without changing the saved records.

The artifact was trained only on synthetic, unvalidated proposed labels. Its perfect group-aware score is a synthetic pipeline smoke-test result, not evidence of real-world audience prediction. The `class_scores` are uncalibrated model scores from `predict_proba`; they are not calibrated probabilities, verified audience facts, or performance estimates. Do not present the model as production-ready.

## Local setup (Windows PowerShell)

In PowerShell, from the repository root, install the backend requirements, which include the pinned inference dependencies. Start the server from `backend` so its existing `.env` is loaded:

```powershell
Set-Location .\backend
.\venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The classifier uses synthetic proposed labels and is not validated for real audience prediction. Never use joblib artifacts from untrusted sources.


