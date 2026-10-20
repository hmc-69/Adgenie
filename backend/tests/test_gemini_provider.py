import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from google.genai.errors import ServerError

from app.routers.creative import router
from app.schemas.creative import ImageCreativeBrief, VideoCreativeScript
from app.services.creative.providers.gemini_provider import GeminiCreativeProvider
from app.services.creative.providers.mock_provider import MockCreativeProvider
from app.services.creative.text_generator import get_provider
from app.services.creative.text_generator import generate_image_brief
from app.services.creative_service import get_owned_campaign
from app.core.config import settings


class GeminiProviderTests(unittest.TestCase):
    def setUp(self):
        self.campaign = {
            "name": "Summer Audio Launch",
            "product_name": "Wireless Earbuds",
            "description": "Premium wireless earbuds for students.",
            "target_audience": "Students and commuters",
            "platform": "Instagram",
            "objective": "Product Promotion",
            "tone": "Exciting",
            "keywords": "music, wireless, students",
        }

    def test_mock_provider_selection_still_works(self):
        with patch.object(settings, "AI_PROVIDER", "mock"):
            self.assertIsInstance(get_provider(), MockCreativeProvider)

    def test_gemini_provider_selection_and_initialization(self):
        with patch.object(settings, "AI_PROVIDER", "gemini"), patch.object(
            settings, "GEMINI_API_KEY", "test-key"
        ), patch("app.services.creative.providers.gemini_provider.genai.Client") as client:
            provider = get_provider()

        self.assertIsInstance(provider, GeminiCreativeProvider)
        client.assert_called_once_with(api_key="test-key")
        self.assertEqual(provider.model, settings.GEMINI_MODEL)

    def test_missing_gemini_api_key_is_rejected(self):
        with patch.object(settings, "GEMINI_API_KEY", None):
            with self.assertRaisesRegex(ValueError, "GEMINI_API_KEY"):
                GeminiCreativeProvider()

    def test_structured_image_response_is_validated(self):
        parsed = ImageCreativeBrief(
            headline="Listen differently",
            primary_text="Premium sound for daily commutes.",
            description="Wireless earbuds for students and commuters.",
            call_to_action="Learn More",
            hashtags=["#WirelessEarbuds"],
            visual_direction="A bright commuter lifestyle scene with the earbuds in focus.",
        )
        response = Mock(parsed=parsed)
        with patch.object(settings, "GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client:
            client.return_value.models.generate_content.return_value = response
            result = GeminiCreativeProvider().generate_image_brief(self.campaign)

        self.assertEqual(result, parsed.model_dump())
        request = client.return_value.models.generate_content.call_args.kwargs
        self.assertEqual(request["config"].response_mime_type, "application/json")
        self.assertIs(request["config"].response_schema, ImageCreativeBrief)

    def test_image_brief_uses_mock_fallback_when_gemini_is_unavailable(self):
        error = ServerError(503, {"error": {"status": "UNAVAILABLE"}}, None)
        with patch.object(settings, "AI_PROVIDER", "gemini"), patch.object(
            settings, "AI_FALLBACK_TO_MOCK", True
        ), patch.object(settings, "GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client:
            client.return_value.models.generate_content.side_effect = error
            result = generate_image_brief(self.campaign)

        self.assertIn("headline", result)
        self.assertIn("visual_direction", result)

    def test_image_brief_does_not_fallback_for_non_server_errors(self):
        with patch.object(settings, "AI_PROVIDER", "gemini"), patch.object(
            settings, "AI_FALLBACK_TO_MOCK", True
        ), patch.object(settings, "GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client:
            client.return_value.models.generate_content.side_effect = ValueError("bad response")
            with self.assertRaisesRegex(ValueError, "bad response"):
                generate_image_brief(self.campaign)

    def test_structured_video_response_is_validated(self):
        parsed = VideoCreativeScript(
            title="Wireless Earbuds for Every Day",
            duration=15,
            scenes=[
                {
                    "scene_number": 1,
                    "duration": 7,
                    "visual": "A student starts a commute.",
                    "visual_description": "Landscape photo of a student wearing earbuds on a city commute.",
                    "visual_prompt": "Landscape photo of a commuter listening to earbuds in a bright train station, no text or logos.",
                    "voiceover": "Bring your sound with you.",
                    "on_screen_text": "Sound on.",
                },
                {
                    "scene_number": 2,
                    "duration": 8,
                    "visual": "Product close-up and final brand card.",
                    "visual_description": "Landscape close-up of wireless earbuds on a clean desk.",
                    "visual_prompt": "Landscape close-up of wireless earbuds on a bright desk, natural side lighting, no text or logos.",
                    "voiceover": "Shop now for better everyday sound.",
                    "on_screen_text": "Shop Now",
                }
            ],
            final_cta="Shop Now",
        )
        response = Mock(parsed=parsed)
        with patch.object(settings, "GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client:
            client.return_value.models.generate_content.return_value = response
            result = GeminiCreativeProvider().generate_video_script(self.campaign)

        self.assertEqual(result, parsed.model_dump())
        self.assertIs(
            client.return_value.models.generate_content.call_args.kwargs["config"].response_schema["type"],
            "OBJECT",
        )

    def test_invalid_gemini_video_response_is_retried_and_rejected(self):
        invalid = Mock(
            parsed={
                "title": "Too long",
                "duration": 16,
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration": 8,
                        "visual": "Product shot",
                        "visual_description": "Landscape photo of product use.",
                        "visual_prompt": "Landscape context photo of the product in use, no text.",
                        "voiceover": "Too long.",
                        "on_screen_text": "Product",
                    },
                    {
                        "scene_number": 2,
                        "duration": 8,
                        "visual": "CTA shot",
                        "visual_description": "Landscape product photo with open space for caption.",
                        "visual_prompt": "Landscape product photo with clean open space, no text.",
                        "voiceover": "Buy now.",
                        "on_screen_text": "Buy Now",
                    },
                ],
                "final_cta": "Buy Now",
            }
        )
        with patch.object(settings, "GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client:
            client.return_value.models.generate_content.return_value = invalid
            with self.assertRaisesRegex(ValueError, "invalid video script after one retry"):
                GeminiCreativeProvider().generate_video_script(self.campaign)

        self.assertEqual(client.return_value.models.generate_content.call_count, 2)
        retry_prompt = " ".join(client.return_value.models.generate_content.call_args.kwargs["contents"].split())
        self.assertIn("final_cta must exactly match", retry_prompt)

    def test_final_cta_mismatch_is_retried_without_weakening_schema_validation(self):
        invalid = Mock(
            parsed={
                "title": "Wireless earbuds campaign",
                "duration": 10,
                "scenes": [
                    {
                        "scene_number": 1,
                        "duration": 5,
                        "visual": "A person starts a commute.",
                        "visual_description": "Landscape commute photo.",
                        "visual_prompt": "Landscape candid commute photo, no text.",
                        "voiceover": "Take your sound with you.",
                        "on_screen_text": "Start listening",
                    },
                    {
                        "scene_number": 2,
                        "duration": 5,
                        "visual": "Product close-up.",
                        "visual_description": "Landscape product close-up.",
                        "visual_prompt": "Landscape product close-up, no text.",
                        "voiceover": "Shop now.",
                        "on_screen_text": "Shop Today",
                    },
                ],
                "final_cta": "Shop Now",
            }
        )
        with patch.object(settings, "GEMINI_API_KEY", "test-key"), patch(
            "app.services.creative.providers.gemini_provider.genai.Client"
        ) as client:
            client.return_value.models.generate_content.return_value = invalid
            with self.assertRaisesRegex(ValueError, "invalid video script after one retry"):
                GeminiCreativeProvider().generate_video_script(self.campaign)

        self.assertEqual(client.return_value.models.generate_content.call_count, 2)
        retry_prompt = " ".join(client.return_value.models.generate_content.call_args.kwargs["contents"].split())
        self.assertIn("final_cta must exactly match", retry_prompt)

    def test_creative_routes_require_authentication_dependency(self):
        protected_paths = {
            "/api/creative/image-brief",
            "/api/creative/video-script",
            "/api/creative/image",
            "/api/creative/campaign/{campaign_id}/image/{creative_id}",
        }
        for route in router.routes:
            if route.path in protected_paths:
                dependency_callables = {dependency.call for dependency in route.dependant.dependencies}
                self.assertTrue(any(callable.__name__ == "get_current_user" for callable in dependency_callables))

    def test_campaign_ownership_is_enforced(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None

        with self.assertRaises(HTTPException) as context:
            get_owned_campaign(db, campaign_id=99, user_id=7)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Campaign not found")


if __name__ == "__main__":
    unittest.main()
