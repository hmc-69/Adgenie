# Experimental audience classifier inference

The backend audience-analysis endpoint can optionally attach the `result.model_prediction` object. It is **disabled by default** with `AUDIENCE_CLASSIFIER_ENABLED=false`. Set it to `true` only for an explicitly experimental deployment. When enabled, prediction is performed by the local TF-IDF + Logistic Regression artifact at:

backend/datasets/audience_analysis/experimental_output/synthetic-run-20261020T145421Z-seed-42/tfidf_logistic_regression.joblib

The loader accepts only that fixed group-aware artifact. It validates manifest status, target, feature list, classes, split metadata, source dataset hash, Python major/minor, exact scikit-learn/joblib versions, and a pinned SHA-256 for the model binary. It never loads a user-supplied path and does not fall back to Gemini or the mock provider for the prediction. With the feature enabled, a missing or incompatible artifact produces HTTP 503 before the narrative provider is called.

The existing provider still creates the audience overview, segments, targeting and messaging recommendations. The classifier prediction is kept in a separate optional field and does not determine or rewrite those recommendations. Existing frontend clients can ignore this additive field; saved historical results without it remain valid.

The artifact was trained only on synthetic, unvalidated proposed labels. Its perfect group-aware score is a synthetic pipeline smoke-test result, not evidence of real-world audience prediction. The `class_scores` are uncalibrated model scores from `predict_proba`; they are not calibrated probabilities, verified audience facts, or performance estimates. Do not present the model as production-ready.

## Local setup (Windows PowerShell)

In PowerShell, from the repository root, install the pinned experimental ML dependencies into the backend virtual environment only if you deliberately want to exercise the opt-in path. Start the server from `backend` so its existing `.env` is loaded:

```powershell
Set-Location .\backend
.\venv\Scripts\python.exe -m pip install -r .\datasets\audience_analysis\requirements-experimental.txt
$env:AUDIENCE_CLASSIFIER_ENABLED = 'true'
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Otherwise leave the flag false; the existing recommendation workflow is unchanged. Never use joblib artifacts from untrusted sources.


