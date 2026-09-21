import unittest

from app.services.creative.text_generator import generate_image_brief, generate_video_script


class CreativeGenerationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
