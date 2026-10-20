import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.campaign import Campaign
from app.models.user import User
from app.models.audience_analysis import AudienceAnalysisRun
from app.routers.audience_analysis import router
from app.routers.auth import get_current_user
from app.schemas.audience_analysis import (
    AudienceAnalysisProviderResult,
    AudienceAnalysisResult,
    AudienceAnalysisRunResponse,
)
from app.services.creative.providers.gemini_provider import GeminiCreativeProvider
from app.services.audience_classifier import AudienceClassifierError


VALID_RESULT = {
    "audience_overview": "Potential customers interested in practical wireless audio.",
    "segments": [
        {
            "name": "Daily commuters",
            "description": "People who listen to audio while commuting.",
            "relevant_interests": ["commuting", "music"],
            "needs_pain_points": ["Convenient listening during travel."],
            "motivations": ["A comfortable audio option for daily routines."],
            "recommended_message_angle": "Show how the product fits into a commute.",
        },
        {
            "name": "Students",
            "description": "Students looking for audio products for study and leisure.",
            "relevant_interests": ["education", "music"],
            "needs_pain_points": ["A product that fits study and travel routines."],
            "motivations": ["Learn whether the product meets their needs."],
            "recommended_message_angle": "Use factual product details in student contexts.",
        },
    ],
    "targeting_approaches": [
        {
            "platform": "Instagram",
            "approaches": ["Test relevant interest groups where available."],
        }
    ],
    "messaging_recommendations": ["Use only benefits supported by the campaign brief."],
    "creative_considerations": ["Use a clear product-focused visual."],
    "assumptions": ["The audience description reflects the campaign team's current hypothesis."],
    "limitations": ["No platform audience data was accessed."],
    "missing_information": ["Customer research would help validate these segments."],
}


class AudienceAnalysisApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = self.Session()
        self.owner = User(name="Owner", email="owner@example.test", password_hash="hash")
        self.other_user = User(name="Other", email="other@example.test", password_hash="hash")
        self.db.add_all([self.owner, self.other_user])
        self.db.flush()
        self.campaign = Campaign(
            user_id=self.owner.id,
            name="Audio launch",
            product_name="Wireless earbuds",
            description="Premium wireless earbuds for everyday listening.",
            target_audience="Students and commuters",
            platform="Instagram",
            objective="Product Promotion",
            tone="Friendly",
            keywords="audio, commute",
            budget=None,
            status="Draft",
        )
        self.db.add(self.campaign)
        self.db.commit()

        self.app = FastAPI()
        self.app.include_router(router)

        def override_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_db
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=self.owner.id)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_successful_analysis_persists_and_history_retrieves_valid_schema(self):
        provider = Mock()
        provider.generate_audience_analysis.return_value = VALID_RESULT
        with patch("app.services.audience_analysis_service.get_provider", return_value=provider), patch(
            "app.services.audience_analysis_service.settings.AI_PROVIDER", "mock"
        ):
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["campaign_id"], self.campaign.id)
        self.assertEqual(payload["analysis_type"], "audience_analysis")
        self.assertEqual(payload["input_snapshot"]["product_name"], "Wireless earbuds")
        self.assertIsNone(payload["input_snapshot"]["budget"])
        self.assertIn("not verified audience data", payload["result"]["recommendation_label"])
        AudienceAnalysisRunResponse.model_validate(payload)
        provider.generate_audience_analysis.assert_called_once()

        history = self.client.get(f"/api/campaigns/{self.campaign.id}/audience-analysis")
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()["total"], 1)
        self.assertEqual(history.json()["analyses"][0]["id"], payload["id"])

    def test_post_route_logs_request_receipt_without_request_data(self):
        provider = Mock()
        provider.generate_audience_analysis.return_value = VALID_RESULT
        with patch("app.services.audience_analysis_service.get_provider", return_value=provider), self.assertLogs(
            "app.routers.audience_analysis", level="INFO"
        ) as logs:
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")

        self.assertEqual(response.status_code, 201, response.text)
        self.assertIn("POST received for campaign_id=1", " ".join(logs.output))

    def test_incomplete_campaign_context_is_passed_without_requiring_optional_fields(self):
        self.campaign.keywords = None
        self.campaign.budget = None
        self.db.commit()
        provider = Mock()
        provider.generate_audience_analysis.return_value = VALID_RESULT
        with patch("app.services.audience_analysis_service.get_provider", return_value=provider):
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")
        self.assertEqual(response.status_code, 201, response.text)
        snapshot = provider.generate_audience_analysis.call_args.args[0]
        self.assertIsNone(snapshot["keywords"])
        self.assertIsNone(snapshot["budget"])

    def test_invalid_model_output_returns_clear_gateway_error(self):
        provider = Mock()
        provider.generate_audience_analysis.return_value = {"audience_overview": "Incomplete"}
        with patch("app.services.audience_analysis_service.get_provider", return_value=provider):
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")
        self.assertEqual(response.status_code, 502)
        self.assertIn("invalid audience analysis", response.json()["detail"])
        self.assertNotIn("key", response.json()["detail"].lower())

    def test_invalid_provider_field_logs_safe_validation_location_and_message(self):
        malformed = {**VALID_RESULT, "segments": [{**VALID_RESULT["segments"][0], "relevant_interests": "commuting"}, VALID_RESULT["segments"][1]]}
        provider = Mock()
        provider.generate_audience_analysis.return_value = malformed
        with patch("app.services.audience_analysis_service.get_provider", return_value=provider), self.assertLogs(
            "app.services.audience_analysis_service", level="WARNING"
        ) as logs:
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")

        self.assertEqual(response.status_code, 502)
        diagnostic = " ".join(logs.output)
        self.assertIn("segments.0.relevant_interests", diagnostic)
        self.assertIn("valid list", diagnostic)
        self.assertNotIn("commuting", diagnostic)

    def test_provider_failure_returns_service_unavailable(self):
        provider = Mock()
        provider.generate_audience_analysis.side_effect = RuntimeError("private provider detail")
        with patch("app.services.audience_analysis_service.get_provider", return_value=provider):
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private provider detail", response.text)

    def test_enabled_classifier_prediction_is_added_as_separate_response_metadata(self):
        provider = Mock()
        provider.generate_audience_analysis.return_value = VALID_RESULT
        prediction = {
            "predicted_archetype": "convenience_seekers",
            "model_identifier": "test-model",
            "model_status": "synthetic_experiment_only",
            "class_scores": {"convenience_seekers": 0.7},
            "score_type": "uncalibrated model score",
        }
        with patch("app.services.audience_analysis_service.settings.AUDIENCE_CLASSIFIER_ENABLED", True), patch(
            "app.services.audience_analysis_service.predict_audience_archetype", return_value=prediction
        ), patch("app.services.audience_analysis_service.get_provider", return_value=provider):
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["result"]["model_prediction"], prediction)
        self.assertEqual(self.db.query(AudienceAnalysisRun).count(), 1)

    def test_missing_enabled_classifier_does_not_call_text_provider_as_fallback(self):
        provider = Mock()
        with patch("app.services.audience_analysis_service.settings.AUDIENCE_CLASSIFIER_ENABLED", True), patch(
            "app.services.audience_analysis_service.predict_audience_archetype",
            side_effect=AudienceClassifierError("missing"),
        ), patch("app.services.audience_analysis_service.get_provider", return_value=provider) as get_provider:
            response = self.client.post(f"/api/campaigns/{self.campaign.id}/audience-analysis")

        self.assertEqual(response.status_code, 503)
        self.assertIn("classifier is enabled", response.json()["detail"])
        get_provider.assert_not_called()

    def test_missing_campaign_returns_not_found(self):
        response = self.client.post("/api/campaigns/9999/audience-analysis")
        self.assertEqual(response.status_code, 404)

    def test_main_app_registers_both_expected_audience_analysis_methods(self):
        from app.main import app

        path = "/api/campaigns/{campaign_id}/audience-analysis"
        operations = app.openapi()["paths"].get(path)
        self.assertIsNotNone(operations)
        self.assertIn("get", operations)
        self.assertIn("post", operations)
        self.assertNotIn("/api/api/campaigns/{campaign_id}/audience-analysis", app.openapi()["paths"])

    def test_campaign_owned_by_another_user_is_not_accessible(self):
        other_campaign = Campaign(
            user_id=self.other_user.id,
            name="Other campaign",
            product_name="Product",
            description="Description",
            target_audience="Audience",
            platform="Facebook",
            objective="Brand Awareness",
            tone="Professional",
            status="Draft",
        )
        self.db.add(other_campaign)
        self.db.commit()
        response = self.client.get(f"/api/campaigns/{other_campaign.id}/audience-analysis")
        self.assertEqual(response.status_code, 404)

    def test_result_schema_rejects_single_segment_and_missing_fields(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            AudienceAnalysisResult.model_validate({"audience_overview": "Only partial output"})

    def test_gemini_audience_analysis_uses_existing_structured_client(self):
        parsed = Mock(parsed=VALID_RESULT)
        with patch("app.core.config.settings.GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client:
            client.return_value.models.generate_content.return_value = parsed
            provider = GeminiCreativeProvider()
            result = provider.generate_audience_analysis({"product_name": "Wireless earbuds"})

        self.assertEqual(result["audience_overview"], VALID_RESULT["audience_overview"])
        request = client.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(request["model"], provider.model)
        self.assertEqual(request["config"].response_mime_type, "application/json")
        self.assertIs(request["config"].response_schema, AudienceAnalysisProviderResult)
        self.assertNotIn("model_prediction", AudienceAnalysisProviderResult.model_json_schema()["properties"])

    def test_gemini_validation_logs_safe_schema_diagnostics(self):
        parsed = Mock(parsed={"audience_overview": "partial"})
        with patch("app.core.config.settings.GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client, self.assertLogs("app.services.creative.providers.gemini_provider", level="WARNING") as logs:
            client.return_value.models.generate_content.return_value = parsed
            provider = GeminiCreativeProvider()
            with self.assertRaisesRegex(ValueError, "invalid structured content"):
                provider.generate_audience_analysis({"product_name": "Wireless earbuds"})

        diagnostic = " ".join(logs.output)
        self.assertIn("segments", diagnostic)
        self.assertIn("missing", diagnostic)
        self.assertNotIn("Wireless earbuds", diagnostic)


if __name__ == "__main__":
    unittest.main()
