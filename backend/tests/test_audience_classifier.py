import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from app.services import audience_classifier as classifier


LABELS = sorted(classifier.ALLOWED_LABELS)


class FakePipeline:
    def __init__(self, predicted):
        self.named_steps = {
            "tfidf": object(),
            "classifier": SimpleNamespace(classes_=LABELS),
        }
        self.predicted = predicted

    def predict(self, _texts):
        return [self.predicted]

    def predict_proba(self, _texts):
        return [[1.0 / len(LABELS)] * len(LABELS)]


def valid_manifest():
    return {
        "status": "synthetic_experiment_only",
        "dataset_path": "D:\\projects\\AdGenie\\backend\\datasets\\audience_analysis\\synthetic_audience_drafts_v3.csv",
        "dataset_sha256": "test-hash",
        "seed": 42,
        "feature_columns": list(classifier.FEATURE_COLUMNS),
        "target_column": "dominant_archetype",
        "class_mapping": {label: index for index, label in enumerate(LABELS)},
        "python_version": "3.14.5",
        "dependency_versions": {"scikit-learn": "1.8.0", "joblib": "1.6.0"},
        "scikit_learn_version": "1.8.0",
        "artifact_trust": "Trusted local output created by this script. Never load arbitrary pickle/joblib files.",
        "evaluation_splits": {
            "group_aware": {
                "group_overlap_count": 0,
                "model_artifact": classifier.MODEL_FILENAME,
                "split_method": "deterministic group-aware stratified holdout",
            }
        },
    }


class AudienceClassifierTests(unittest.TestCase):
    def setUp(self):
        classifier._load_expected_model.cache_clear()
        self.temp = tempfile.TemporaryDirectory()
        self.analysis_root = Path(self.temp.name) / "audience_analysis"
        self.root = self.analysis_root / "experimental_output" / "synthetic-run-20261020T145421Z-seed-42"
        self.root.mkdir(parents=True)
        (self.analysis_root / "synthetic_audience_drafts_v3.csv").write_text("fixture", encoding="utf-8")
        manifest = valid_manifest()
        import hashlib

        manifest["dataset_sha256"] = hashlib.sha256(b"fixture").hexdigest()
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        metrics = {
            "status": "synthetic_experiment_only",
            "primary_evaluation": "group_aware",
            "evaluations": {"group_aware": {"group_overlap_count": 0, "model_artifact": classifier.MODEL_FILENAME}},
        }
        (self.root / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (self.root / classifier.MODEL_FILENAME).write_bytes(b"trusted test fixture")

    def tearDown(self):
        classifier._load_expected_model.cache_clear()
        self.temp.cleanup()

    def install_fake_model(self, model):
        fake_joblib = ModuleType("joblib")
        fake_joblib.load = lambda _path: model
        self.modules = patch.dict(sys.modules, {"joblib": fake_joblib})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_loads_expected_local_model_and_predicts_each_allowed_class(self):
        with patch.object(classifier, "ARTIFACT_ROOT", self.root), patch.object(classifier, "_check_runtime"):
            for label in LABELS:
                classifier._load_expected_model.cache_clear()
                self.install_fake_model(FakePipeline(label))
                with patch.object(classifier, "MODEL_SHA256", hashlib.sha256(b"trusted test fixture").hexdigest()):
                    prediction = classifier.predict_audience_archetype(
                        {"product_name": "Field notebook", "description": "Made for daily use"}
                    )
                self.assertEqual(prediction["predicted_archetype"], label)
                self.assertEqual(set(prediction["class_scores"]), classifier.ALLOWED_LABELS)
                self.assertEqual(prediction["model_status"], "synthetic_experiment_only")
                self.assertIn("uncalibrated", prediction["score_type"])

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(classifier.AudienceClassifierError):
            classifier.predict_audience_archetype({"product_name": 123})
        with self.assertRaises(classifier.AudienceClassifierError):
            classifier.predict_audience_archetype({"target_audience": "Students"})

    def test_missing_manifest_fails_clearly(self):
        with patch.object(classifier, "ARTIFACT_ROOT", self.root / "missing"):
            with self.assertRaisesRegex(classifier.AudienceClassifierError, "manifest"):
                classifier._read_manifest(classifier.ARTIFACT_ROOT)

    def test_missing_model_artifact_fails_before_joblib_load(self):
        (self.root / classifier.MODEL_FILENAME).unlink()
        with patch.object(classifier, "ARTIFACT_ROOT", self.root), patch.object(classifier, "_check_runtime"):
            with self.assertRaisesRegex(classifier.AudienceClassifierError, "missing or invalid"):
                classifier._load_expected_model()

    def test_malformed_manifest_is_rejected(self):
        (self.root / "manifest.json").write_text("{bad json", encoding="utf-8")
        with self.assertRaisesRegex(classifier.AudienceClassifierError, "manifest"):
            classifier._read_manifest(self.root)

    def test_manifest_feature_mismatch_is_rejected(self):
        manifest = valid_manifest()
        manifest["feature_columns"] = ["description", "target_audience"]
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(classifier.AudienceClassifierError, "incompatible"):
            classifier._read_manifest(self.root)

    def test_wrong_pipeline_classes_are_rejected(self):
        model = FakePipeline(LABELS[0])
        model.named_steps["classifier"].classes_ = ["unknown"]
        with patch.object(classifier, "ARTIFACT_ROOT", self.root), patch.object(classifier, "_check_runtime"), patch.object(
            classifier, "MODEL_SHA256", hashlib.sha256(b"trusted test fixture").hexdigest()
        ), patch.dict(sys.modules, {"joblib": SimpleNamespace(load=lambda _path: model)}):
            with self.assertRaisesRegex(classifier.AudienceClassifierError, "does not match"):
                classifier._load_expected_model()


if __name__ == "__main__":
    unittest.main()
