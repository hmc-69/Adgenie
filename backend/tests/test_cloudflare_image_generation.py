import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.schemas.creative import ImageGenerationRequest
from app.services.creative.providers.cloudflare_image_provider import (
    CloudflareImageProviderError,
    GeneratedImage,
)
from app.services.creative_service import generate_ad_image_for_creative


class CloudflareImageGenerationTests(unittest.TestCase):
    def setUp(self):
        self.campaign = SimpleNamespace(
            id=4,
            name="Summer Audio Launch",
            product_name="Wireless Earbuds",
            description="Premium wireless earbuds for students.",
            target_audience="Students and commuters",
            platform="Instagram",
            objective="Product Promotion",
            tone="Exciting",
            keywords="music, wireless, students",
        )
        self.creative = SimpleNamespace(
            id=9,
            campaign_id=4,
            type="image",
            generated_content={
                "headline": "Hear the Summer Spirit",
                "primary_text": "Premium sound for the daily commute.",
                "description": "Wireless earbuds for students.",
                "call_to_action": "Shop Now",
                "hashtags": ["#SummerAudio"],
                "visual_direction": "Students listening to music on the move.",
            },
            image_url=None,
            image_path=None,
            image_content_type=None,
            image_aspect_ratio=None,
            image_style=None,
            image_resolution=None,
            generated_at=None,
        )
        self.db = Mock()
        self.db.query.return_value.filter.return_value.first.side_effect = [
            self.campaign,
            self.campaign,
            self.creative,
        ]

    def test_generates_and_persists_cloudflare_image_metadata(self):
        provider = Mock()
        provider.generate_image.return_value = GeneratedImage(b"jpeg-bytes", "image/jpeg")
        storage_service = Mock()
        storage_service.upload_image.return_value = (
            "campaigns/4/creatives/9/unique-image.jpg"
        )
        with patch("app.services.creative_service.get_image_provider", return_value=provider):
            with patch(
                "app.services.creative_service.get_supabase_storage_service",
                return_value=storage_service,
            ):
                result = generate_ad_image_for_creative(
                    self.db,
                    campaign_id=4,
                    creative_id=9,
                    user_id=12,
                    aspect_ratio="4:5",
                    style="Photographic",
                )

            provider.generate_image.assert_called_once()
            self.assertEqual(provider.generate_image.call_args.kwargs, {"aspect_ratio": "4:5"})
            prompt = provider.generate_image.call_args.args[0]
            self.assertIn("Hear the Summer Spirit", prompt)
            self.assertIn("Aspect ratio: 4:5", prompt)
            self.assertIn("Photographic", prompt)
            storage_service.upload_image.assert_called_once_with(
                image_bytes=b"jpeg-bytes",
                content_type="image/jpeg",
                campaign_id=4,
                creative_id=9,
            )
            self.assertEqual(
                self.creative.image_path,
                "campaigns/4/creatives/9/unique-image.jpg",
            )
            self.assertEqual(self.creative.image_content_type, "image/jpeg")
            self.assertEqual(self.creative.image_url, "/api/creative/campaign/4/image/9")
            self.assertEqual(self.creative.image_aspect_ratio, "4:5")
            self.assertEqual(self.creative.image_style, "Photographic")
            self.assertEqual(result["creative_id"], 9)
            self.assertNotIn("image_path", result)
            self.db.commit.assert_called_once()

    def test_cloudflare_failure_returns_sanitized_gateway_error(self):
        provider = Mock()
        provider.generate_image.side_effect = CloudflareImageProviderError("Worker failed with secret details")
        with patch("app.services.creative_service.get_image_provider", return_value=provider):
            with self.assertRaises(HTTPException) as context:
                generate_ad_image_for_creative(
                    self.db,
                    campaign_id=4,
                    creative_id=9,
                    user_id=12,
                    aspect_ratio="1:1",
                    style="Minimal",
                )

        self.assertEqual(context.exception.status_code, 502)
        self.assertNotIn("secret", context.exception.detail)
        self.db.commit.assert_not_called()

    def test_creative_from_another_campaign_is_rejected_before_provider_call(self):
        self.db.query.return_value.filter.return_value.first.side_effect = [self.campaign, None]
        with patch("app.services.creative_service.get_image_provider") as get_provider:
            with self.assertRaises(HTTPException) as context:
                generate_ad_image_for_creative(
                    self.db,
                    campaign_id=4,
                    creative_id=99,
                    user_id=12,
                    aspect_ratio="1:1",
                    style="Minimal",
                )

        self.assertEqual(context.exception.status_code, 404)
        get_provider.assert_not_called()

    def test_request_rejects_unsupported_aspect_ratio_and_style(self):
        with self.assertRaises(ValueError):
            ImageGenerationRequest(
                campaign_id=4,
                creative_id=9,
                aspect_ratio="2:1",
                style="Photographic",
            )
        with self.assertRaises(ValueError):
            ImageGenerationRequest(
                campaign_id=4,
                creative_id=9,
                aspect_ratio="1:1",
                style="Unlisted style",
            )


if __name__ == "__main__":
    unittest.main()