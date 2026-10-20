import unittest

from pydantic import ValidationError

from app.schemas.creative import VideoCreativeScript


def make_script(duration=15, first_duration=7, second_duration=8):
    return {
        "title": "Product launch",
        "duration": duration,
        "scenes": [
            {
                "scene_number": 1,
                "duration": first_duration,
                "visual": "A product lifestyle shot.",
                "visual_description": "Landscape photo of a student using the product on a commute.",
                "voiceover": "Meet the product.",
                "on_screen_text": "Meet it",
            },
            {
                "scene_number": 2,
                "duration": second_duration,
                "visual": "A final product shot.",
                "visual_description": "Landscape product close-up with clean lighting.",
                "voiceover": "Try it today.",
                "on_screen_text": "Try Now",
            },
        ],
        "final_cta": "Try Now",
    }


class VideoScriptSchemaTests(unittest.TestCase):
    def test_gemini_schema_does_not_use_unsupported_exclusive_minimum(self):
        schema = VideoCreativeScript.model_json_schema()

        def contains_exclusive_minimum(value):
            if isinstance(value, dict):
                return "exclusiveMinimum" in value or any(
                    contains_exclusive_minimum(item) for item in value.values()
                )
            if isinstance(value, list):
                return any(contains_exclusive_minimum(item) for item in value)
            return False

        self.assertFalse(contains_exclusive_minimum(schema))

    def test_script_totalling_15_seconds_is_valid(self):
        script = VideoCreativeScript.model_validate(make_script())
        self.assertEqual(script.duration, 15)

    def test_script_totalling_less_than_15_seconds_is_valid(self):
        script = VideoCreativeScript.model_validate(make_script(12, 5, 7))
        self.assertEqual(script.duration, 12)

    def test_script_exceeding_15_seconds_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "15"):
            VideoCreativeScript.model_validate(make_script(16, 8, 8))

    def test_scene_duration_must_be_numeric_and_positive(self):
        invalid = make_script()
        del invalid["scenes"][0]["duration"]
        with self.assertRaises(ValidationError):
            VideoCreativeScript.model_validate(invalid)

        invalid = make_script()
        invalid["scenes"][0]["duration"] = "0-5 seconds"
        with self.assertRaises(ValidationError):
            VideoCreativeScript.model_validate(invalid)

        invalid = make_script()
        invalid["scenes"][0]["duration"] = 0
        with self.assertRaises(ValidationError):
            VideoCreativeScript.model_validate(invalid)

    def test_top_level_duration_must_match_scene_total(self):
        with self.assertRaisesRegex(ValidationError, "equal the sum"):
            VideoCreativeScript.model_validate(make_script(15, 5, 5))

    def test_final_scene_must_contain_cta(self):
        invalid = make_script()
        invalid["scenes"][1]["on_screen_text"] = "Product"
        with self.assertRaisesRegex(ValidationError, "final scene"):
            VideoCreativeScript.model_validate(invalid)


if __name__ == "__main__":
    unittest.main()
