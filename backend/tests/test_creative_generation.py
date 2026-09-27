import unittest
from unittest.mock import patch

from app.services.creative.text_generator import (
    build_image_generation_prompt,
    generate_image_brief,
    generate_video_script,
    get_supported_image_resolutions,
)


class CreativeGenerationTests(unittest.TestCase):
    def setUp(self):
        self.provider_patch = patch("app.core.config.settings.AI_PROVIDER", "mock")
        self.provider_patch.start()

    def tearDown(self):
        self.provider_patch.stop()

    def test_generate_image_brief_contains_required_fields(self):
        campaign = {
            "name": "Summer Audio Launch",
            "product_name": "Wireless Earbuds",
            "description": "Premium wireless earbuds for students.",
            "target_audience": "Students and commuters",
            "platform": "Instagram",
            "objective": "Product Promotion",
            "tone": "Exciting",
            "keywords": "music, wireless, students",
        }

        brief = generate_image_brief(campaign)

        self.assertIn("headline", brief)
        self.assertIn("primary_text", brief)
        self.assertIn("description", brief)
        self.assertIn("call_to_action", brief)
        self.assertIn("hashtags", brief)
        self.assertIn("visual_direction", brief)
        self.assertIsInstance(brief["hashtags"], list)

    def test_generate_video_script_contains_required_fields(self):
        campaign = {
            "name": "Summer Audio Launch",
            "product_name": "Wireless Earbuds",
            "description": "Premium wireless earbuds for students.",
            "target_audience": "Students and commuters",
            "platform": "Instagram",
            "objective": "Product Promotion",
            "tone": "Exciting",
            "keywords": "music, wireless, students",
        }

        script = generate_video_script(campaign)

        self.assertIn("title", script)
        self.assertIn("duration", script)
        self.assertIn("scenes", script)
        self.assertIn("final_cta", script)
        self.assertGreater(len(script["scenes"]), 0)

    def test_build_image_generation_prompt_uses_campaign_and_brief(self):
        campaign = {
            "name": "Summer Audio Launch",
            "product_name": "Wireless Earbuds",
            "description": "Premium wireless earbuds for students.",
            "target_audience": "Students and commuters",
            "platform": "Instagram",
            "objective": "Product Promotion",
            "tone": "Exciting",
            "keywords": "music, wireless, students",
        }
        creative = {
            "headline": "Hear the Summer Spirit",
            "primary_text": "Experience premium sound with zero compromise.",
            "description": "Stay powered all day with a lightweight design.",
            "call_to_action": "Shop Now",
            "hashtags": ["#SummerAudio", "#WirelessSound"],
            "visual_direction": "Lifestyle shot with students on the move.",
        }

        prompt = build_image_generation_prompt(campaign, creative, "4:5", "Photographic", "1K")

        self.assertIn("Summer Audio Launch", prompt)
        self.assertIn("Hear the Summer Spirit", prompt)
        self.assertIn("Photographic", prompt)
        self.assertIn("4:5", prompt)
        self.assertIn("Shop Now", prompt)

    def test_get_supported_image_resolutions_for_default_model(self):
        resolutions = get_supported_image_resolutions()

        self.assertIsInstance(resolutions, list)
        self.assertIn("1K", resolutions)


if __name__ == "__main__":
    unittest.main()
