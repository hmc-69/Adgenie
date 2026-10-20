import unittest
from unittest.mock import Mock, patch

import httpx

from app.schemas.creative import VideoCreativeScript
from app.services.creative.providers.json2video_provider import (
    DEFAULT_VOICE_ID,
    VOICE_MODEL,
    JSON2VideoError,
    JSON2VideoProvider,
)


def valid_script(duration=15):
    return VideoCreativeScript.model_validate({
        "title": "Launch",
        "duration": duration,
        "scenes": [
            {"scene_number": 1, "duration": 7, "visual": "Opening", "visual_description": "Student using earbuds", "voiceover": "Meet it.", "on_screen_text": "Meet it"},
            {"scene_number": 2, "duration": 8, "visual": "Close", "visual_description": "Earbuds close-up", "voiceover": "Try it.", "on_screen_text": "Try Now"},
        ],
        "final_cta": "Try Now",
    }).model_dump()


class JSON2VideoProviderTests(unittest.TestCase):
    def test_valid_15_second_script_maps_to_full_hd_payload(self):
        payload = JSON2VideoProvider.build_movie_payload(
            valid_script(),
            image_urls=["https://cdn.example/opening.jpg", "https://cdn.example/product.png"],
        )
        self.assertNotIn("movie", payload)
        self.assertNotIn("title", payload)
        self.assertEqual(payload["resolution"], "full-hd")
        self.assertEqual(sum(scene["duration"] for scene in payload["scenes"]), 15)
        self.assertEqual(len(payload["scenes"][0]["elements"]), 3)
        self.assertEqual(payload["scenes"][0]["transition"]["type"], "xfade")
        self.assertEqual(payload["scenes"][0]["elements"][0]["type"], "image")
        self.assertEqual(payload["scenes"][0]["elements"][0]["src"], "https://cdn.example/opening.jpg")
        self.assertEqual(payload["scenes"][0]["elements"][0]["duration"], 7)
        self.assertEqual(payload["scenes"][0]["elements"][1]["type"], "voice")
        self.assertEqual(payload["scenes"][0]["elements"][2]["settings"]["color"], "#FFFFFF")
        voice_elements = [
            element
            for scene in payload["scenes"]
            for element in scene["elements"]
            if element["type"] == "voice"
        ]
        self.assertEqual(len(voice_elements), len(payload["scenes"]))
        self.assertEqual([element["text"] for element in voice_elements], ["Meet it.", "Try it."])
        self.assertTrue(all(element["voice"] == DEFAULT_VOICE_ID for element in voice_elements))
        self.assertTrue(all(element["model"] == VOICE_MODEL for element in voice_elements))

    def test_missing_or_malformed_scene_image_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Scene 1.*valid public image URL"):
            JSON2VideoProvider.build_movie_payload(valid_script())
        with self.assertRaisesRegex(ValueError, "Scene 2.*valid public image URL"):
            JSON2VideoProvider.build_movie_payload(
                valid_script(),
                scene_assets=[{"image_url": "https://cdn.example/product.jpg"}, {"image_url": "javascript:alert(1)"}],
            )

    def test_image_elements_cover_frame_and_only_caption_is_overlay(self):
        payload = JSON2VideoProvider.build_movie_payload(
            valid_script(),
            scene_assets=[
                {"image_url": "https://cdn.example/product.png"},
                {"image_url": "https://cdn.example/second.jpg"},
            ],
        )
        image_element = payload["scenes"][0]["elements"][0]
        self.assertEqual(image_element, {
            "type": "image", "src": "https://cdn.example/product.png", "resize": "cover", "duration": 7,
        })
        self.assertEqual(payload["scenes"][1]["elements"][0]["src"], "https://cdn.example/second.jpg")
        self.assertEqual([e["text"] for e in payload["scenes"][1]["elements"] if e["type"] == "text"], ["Try Now"])
        self.assertNotIn("fit", image_element)

    def test_invalid_script_is_rejected_before_submission(self):
        invalid = valid_script()
        invalid["duration"] = 16
        with self.assertRaises(ValueError):
            JSON2VideoProvider.build_movie_payload(invalid)

    def test_missing_key_is_rejected(self):
        with patch("app.services.creative.providers.json2video_provider.settings.JSON2VIDEO_API_KEY", None):
            with self.assertRaisesRegex(JSON2VideoError, "not configured"):
                JSON2VideoProvider()

    def test_submission_and_status_use_documented_endpoints(self):
        client = Mock()
        submitted = Mock(status_code=200, is_error=False)
        submitted.json.return_value = {"project": "project-123"}
        status_response = Mock(status_code=200, is_error=False)
        status_response.json.return_value = {
            "success": True,
            "movie": {
                "success": True,
                "project": "project-123",
                "status": "done",
                "url": "https://cdn.example/video.mp4",
                "duration": 14.76,
            },
        }
        client.post.return_value = submitted
        client.get.return_value = status_response
        with patch("app.services.creative.providers.json2video_provider.settings.JSON2VIDEO_API_KEY", "secret"):
            provider = JSON2VideoProvider(client=client)
            result = provider.create_movie(
                valid_script(), image_urls=["https://cdn.example/one.jpg", "https://cdn.example/two.jpg"]
            )
            current = provider.get_movie_status("project-123")

        self.assertEqual(result["project_id"], "project-123")
        self.assertEqual(current["status"], "done")
        self.assertEqual(current["result_url"], "https://cdn.example/video.mp4")
        self.assertEqual(current["project_id"], "project-123")
        self.assertEqual(client.get.call_args.args[0], "/movies")
        self.assertEqual(client.get.call_args.kwargs["params"], {"project": "project-123"})
        client.post.assert_called_once()
        self.assertEqual(client.post.call_args.args[0], "/movies")
        outgoing_payload = client.post.call_args.kwargs["json"]
        self.assertNotIn("movie", outgoing_payload)
        self.assertNotIn("title", outgoing_payload)
        self.assertEqual(set(outgoing_payload), {"resolution", "scenes"})
        self.assertEqual(sum(scene["duration"] for scene in outgoing_payload["scenes"]), 15)
        voice_elements = [
            element
            for scene in outgoing_payload["scenes"]
            for element in scene["elements"]
            if element["type"] == "voice"
        ]
        self.assertEqual(len(voice_elements), len(outgoing_payload["scenes"]))
        self.assertTrue(all(element["voice"] == DEFAULT_VOICE_ID for element in voice_elements))
        self.assertTrue(all(element["model"] == VOICE_MODEL for element in voice_elements))
        self.assertIn("scenes", outgoing_payload)
        self.assertEqual(client.get.call_args.kwargs["params"], {"project": "project-123"})

    def test_create_movie_includes_scene_asset_urls_in_submitted_payload(self):
        client = Mock()
        response = Mock(status_code=200, is_error=False)
        response.json.return_value = {"project": "project-images"}
        client.post.return_value = response
        assets = [
            {"image_url": "https://images.example/opening.jpg"},
            {"image_url": "https://images.example/product.png"},
        ]

        with patch("app.services.creative.providers.json2video_provider.settings.JSON2VIDEO_API_KEY", "secret"):
            result = JSON2VideoProvider(client=client).create_movie(valid_script(), scene_assets=assets)

        payload = client.post.call_args.kwargs["json"]
        image_elements = [
            next(element for element in scene["elements"] if element["type"] == "image")
            for scene in payload["scenes"]
        ]
        self.assertEqual(result["project_id"], "project-images")
        self.assertEqual(
            [element["src"] for element in image_elements],
            [asset["image_url"] for asset in assets],
        )
        self.assertTrue(all(element["resize"] == "cover" for element in image_elements))

    def test_quota_error_is_explicit(self):
        client = Mock()
        response = Mock(status_code=429, is_error=True)
        client.post.return_value = response
        with patch("app.services.creative.providers.json2video_provider.settings.JSON2VIDEO_API_KEY", "secret"):
            with self.assertRaisesRegex(JSON2VideoError, "quota"):
                JSON2VideoProvider(client=client).create_movie(
                    valid_script(), image_urls=["https://cdn.example/one.jpg", "https://cdn.example/two.jpg"]
                )

    def test_provider_rejects_status_for_a_different_project(self):
        client = Mock()
        response = Mock(status_code=200, is_error=False)
        response.json.return_value = {
            "movie": {"project": "another-project", "status": "done", "url": "https://cdn.example/wrong.mp4"}
        }
        client.get.return_value = response

        with patch("app.services.creative.providers.json2video_provider.settings.JSON2VIDEO_API_KEY", "secret"):
            with self.assertRaisesRegex(JSON2VideoError, "different project"):
                JSON2VideoProvider(client=client).get_movie_status("project-123")

    def test_provider_parses_all_documented_movie_statuses(self):
        client = Mock()
        with patch("app.services.creative.providers.json2video_provider.settings.JSON2VIDEO_API_KEY", "secret"):
            provider = JSON2VideoProvider(client=client)
            for status_value in ("pending", "running", "done", "error", "timeout"):
                with self.subTest(status=status_value):
                    response = Mock(status_code=200, is_error=False)
                    response.json.return_value = {
                        "success": True,
                        "movie": {"project": "project-123", "status": status_value, "url": None},
                    }
                    client.get.return_value = response
                    result = provider.get_movie_status("project-123")
                    self.assertEqual(result["project_id"], "project-123")
                    self.assertEqual(result["status"], status_value)


if __name__ == "__main__":
    unittest.main()
