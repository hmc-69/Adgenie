import csv
import json
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.campaign import Campaign
from app.models.campaign_performance import CampaignPerformanceDaily
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.campaign_performance import router
from app.services.campaign_prediction_service import (
    CampaignPredictionArtifactError,
    _load_model_bundle,
    load_model_bundle,
)
from datasets.campaign_performance_prediction.generate_dataset import (
    FEATURES,
    generate_dataset,
    generate_rows,
)
from datasets.campaign_performance_prediction.train_model import (
    FORBIDDEN_FEATURES,
    calculate_metrics,
    split_by_group,
    train_experiment,
)


class CampaignPredictionExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name)
        cls.data_dir = cls.root / "dataset"
        cls.dataset_path, cls.metadata_path = generate_dataset(cls.data_dir, rows=260, seed=72)
        cls.model_root = cls.root / "models"
        cls.training = train_experiment(
            cls.dataset_path,
            cls.model_root,
            version_name="campaign-prediction-test-v1",
            seed=72,
        )
        cls.version_dir = cls.training["version_dir"]

    @classmethod
    def tearDownClass(cls):
        _load_model_bundle.cache_clear()
        cls.temp_dir.cleanup()

    def test_dataset_generation_is_reproducible_and_metadata_checksum_is_valid(self):
        other_dataset, other_metadata = generate_dataset(self.root / "dataset-repeat", rows=260, seed=72)
        self.assertEqual(self.dataset_path.read_bytes(), other_dataset.read_bytes())
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        other = json.loads(other_metadata.read_text(encoding="utf-8"))
        self.assertEqual(metadata["dataset_sha256"], other["dataset_sha256"])
        self.assertEqual(metadata["row_count"], 260)
        self.assertEqual(metadata["feature_columns"], FEATURES)
        self.assertTrue(metadata["synthetic_data"])
        self.assertEqual(len(metadata["dataset_sha256"]), 64)

    def test_synthetic_targets_are_bounded_and_feature_schema_has_no_outcomes_or_ids(self):
        rows = generate_rows(rows=220, seed=15)
        for row in rows:
            self.assertGreaterEqual(row["ctr_percent"], 0)
            self.assertLessEqual(row["ctr_percent"], 100)
            self.assertGreaterEqual(row["conversion_rate_percent"], 0)
            self.assertLessEqual(row["conversion_rate_percent"], 100)
        self.assertFalse(set(FEATURES) & FORBIDDEN_FEATURES)
        self.assertNotIn("scenario_group", FEATURES)
        self.assertNotIn("clicks", FEATURES)
        self.assertNotIn("spend", FEATURES)

    def test_group_aware_splits_are_reproducible_and_isolated(self):
        rows = generate_rows(rows=500, seed=17)
        groups = np.asarray([row["scenario_group"] for row in rows])
        train, validation, test = split_by_group(groups, seed=93)
        repeat = split_by_group(groups, seed=93)
        for left, right in zip((train, validation, test), repeat):
            np.testing.assert_array_equal(left, right)
        train_groups = set(groups[train])
        validation_groups = set(groups[validation])
        test_groups = set(groups[test])
        self.assertFalse(train_groups & validation_groups)
        self.assertFalse(train_groups & test_groups)
        self.assertFalse(validation_groups & test_groups)

    def test_metric_calculation_and_training_compare_baseline_and_estimators(self):
        result = calculate_metrics([1, 2, 3], [1, 2, 4])
        self.assertAlmostEqual(result["mae"], 1 / 3)
        self.assertIn("rmse", result)
        self.assertIn("r2", result)
        evaluations = self.training["metrics"]["evaluation"]
        for target in ("ctr_percent", "conversion_rate_percent"):
            entry = evaluations[target]
            self.assertEqual(set(entry["validation_metrics_by_model"]), {
                "dummy_mean", "linear_regression", "random_forest"
            })
            self.assertIn(entry["selected_model"], entry["validation_metrics_by_model"])
            self.assertIn("mae", entry["test_metrics"])
            self.assertIn("mae", entry["baseline_test_metrics"])
            self.assertIsInstance(entry["meaningful_improvement_over_baseline"], bool)

    def test_model_manifest_checksums_and_trusted_pipeline_reload(self):
        manifest = json.loads((self.version_dir / "manifest.json").read_text(encoding="utf-8"))
        model_file = self.version_dir / "campaign_performance_pipelines.joblib"
        import hashlib
        self.assertEqual(manifest["files"][model_file.name], hashlib.sha256(model_file.read_bytes()).hexdigest())
        self.assertEqual(manifest["model_version"], "campaign-prediction-test-v1")
        with patch.dict(os.environ, {"CAMPAIGN_PERFORMANCE_MODEL_DIR": str(self.model_root)}):
            loaded_manifest, metrics, bundle = load_model_bundle()
        self.assertEqual(loaded_manifest["model_version"], "campaign-prediction-test-v1")
        self.assertEqual(metrics["status"], "synthetic_experiment_only")
        self.assertEqual(set(bundle["models"]), {"ctr_percent", "conversion_rate_percent"})

    def test_manifest_rejects_checksum_mismatch_and_missing_active_model(self):
        artifact = self.version_dir / "campaign_performance_pipelines.joblib"
        original = artifact.read_bytes()
        try:
            artifact.write_bytes(original + b"tampered")
            _load_model_bundle.cache_clear()
            with self.assertRaises(CampaignPredictionArtifactError):
                _load_model_bundle(str(self.model_root.resolve()))
        finally:
            artifact.write_bytes(original)
            _load_model_bundle.cache_clear()
        with tempfile.TemporaryDirectory() as missing_root:
            with self.assertRaises(CampaignPredictionArtifactError):
                _load_model_bundle(str(Path(missing_root).resolve()))


class CampaignPredictionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name)
        cls.data_dir = cls.root / "dataset"
        dataset_path, _ = generate_dataset(cls.data_dir, rows=260, seed=42)
        cls.model_root = cls.root / "models"
        cls.training = train_experiment(
            dataset_path,
            cls.model_root,
            version_name="campaign-prediction-api-test-v1",
            seed=42,
        )

    @classmethod
    def tearDownClass(cls):
        _load_model_bundle.cache_clear()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()
        self.owner = User(name="Owner", email="prediction-owner@example.test", password_hash="hash")
        self.other = User(name="Other", email="prediction-other@example.test", password_hash="hash")
        self.db.add_all([self.owner, self.other])
        self.db.flush()
        self.campaign = self.make_campaign(self.owner.id, "Owned campaign")
        self.other_campaign = self.make_campaign(self.other.id, "Other campaign")
        self.db.add_all([self.campaign, self.other_campaign])
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=self.owner.id)
        self.client = TestClient(self.app)
        self.env_patch = patch.dict(os.environ, {"CAMPAIGN_PERFORMANCE_MODEL_DIR": str(self.model_root)})
        self.env_patch.start()
        _load_model_bundle.cache_clear()

    def make_campaign(self, user_id, name):
        return Campaign(
            user_id=user_id,
            name=name,
            product_name="Wireless earbuds",
            description="A wireless audio product for everyday listening.",
            target_audience="Commuters and students looking for practical audio.",
            platform="Instagram",
            objective="Product Promotion",
            tone="Friendly",
            budget=Decimal("3500.00"),
            keywords="wireless audio; daily commute",
            status="Draft",
        )

    def tearDown(self):
        self.env_patch.stop()
        _load_model_bundle.cache_clear()
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_successful_prediction_uses_campaign_features_and_saved_evaluation(self):
        response = self.client.post(f"/api/campaigns/{self.campaign.id}/performance/predict")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["campaign_id"], self.campaign.id)
        self.assertEqual(payload["prediction_type"], "synthetic_experiment_only")
        self.assertEqual(payload["model_version"], "campaign-prediction-api-test-v1")
        self.assertGreaterEqual(payload["predictions"]["ctr_percent"], 0)
        self.assertLessEqual(payload["predictions"]["ctr_percent"], 100)
        self.assertGreaterEqual(payload["predictions"]["conversion_rate_percent"], 0)
        self.assertLessEqual(payload["predictions"]["conversion_rate_percent"], 100)
        saved = self.training["metrics"]["evaluation"]
        self.assertEqual(payload["evaluation"]["ctr"]["test_mae"], saved["ctr_percent"]["test_metrics"]["mae"])
        self.assertEqual(payload["evaluation"]["ctr"]["baseline_test_mae"], saved["ctr_percent"]["baseline_test_metrics"]["mae"])
        self.assertEqual(payload["evaluation"]["conversion_rate"]["test_r2"], saved["conversion_rate_percent"]["test_metrics"]["r2"])
        self.assertEqual(self.db.query(CampaignPerformanceDaily).count(), 0)

    def test_authentication_ownership_and_nonexistent_campaign_are_enforced(self):
        anonymous_app = FastAPI()
        anonymous_app.include_router(router)
        anonymous_app.dependency_overrides[get_db] = lambda: self.db
        with TestClient(anonymous_app) as anonymous_client:
            anonymous = anonymous_client.post(f"/api/campaigns/{self.campaign.id}/performance/predict")
        self.assertEqual(anonymous.status_code, 401)
        other = self.client.post(f"/api/campaigns/{self.other_campaign.id}/performance/predict")
        missing = self.client.post("/api/campaigns/99999/performance/predict")
        self.assertEqual(other.status_code, 404)
        self.assertEqual(missing.status_code, 404)

    def test_missing_or_invalid_model_artifact_returns_controlled_service_error(self):
        with patch.dict(os.environ, {"CAMPAIGN_PERFORMANCE_MODEL_DIR": str(self.root / "missing-models")}):
            _load_model_bundle.cache_clear()
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/performance/predict")
        self.assertEqual(response.status_code, 503)
        self.assertIn("metadata is missing or invalid", response.json()["detail"])

    def test_invalid_campaign_prediction_features_are_rejected(self):
        self.campaign.platform = "Unsupported Platform"
        self.db.commit()
        response = self.client.post(f"/api/campaigns/{self.campaign.id}/performance/predict")
        self.assertEqual(response.status_code, 422)
        self.assertIn("valid pre-launch", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
