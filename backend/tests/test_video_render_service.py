import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.services.creative_service import start_video_render, update_video_render_status
from app.services.storage.supabase_storage import SupabaseStorageError


SCRIPT = {
    "title": "Launch",
    "duration": 15,
    "scenes": [
        {"scene_number": 1, "duration": 7, "visual": "Opening", "voiceover": "Meet it.", "on_screen_text": "Meet it"},
        {"scene_number": 2, "duration": 8, "visual": "Close", "voiceover": "Try it.", "on_screen_text": "Try Now"},
    ],
    "final_cta": "Try Now",
}


class VideoRenderServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.query.return_value.filter.return_value.all.return_value = []
        self.creative = Mock(
            type="video",
            video_project_id=None,
            video_status=None,
            video_path=None,
            video_duration=None,
            video_result_url=None,
            generated_content=SCRIPT,
        )

    @patch("app.services.creative_service._get_owned_video_creative")
    @patch("app.services.creative_service.PexelsImageSearch")
    @patch("app.services.creative_service.JSON2VideoProvider")
    def test_start_stores_project_id(self, provider_class, search_class, get_creative):
        get_creative.return_value = self.creative
        search_class.return_value.search.side_effect = [
            {"image_url": "https://images.example/one.jpg"},
            {"image_url": "https://images.example/two.jpg"},
        ]
        provider_class.return_value.create_movie.return_value = {
            "project_id": "project-1",
            "status": "submitted",
        }

        result = start_video_render(self.db, 7, 9, 3)

        self.assertEqual(result["project_id"], "project-1")
        self.assertEqual(self.creative.video_duration, 15)
        self.db.commit.assert_called_once()

    @patch("app.services.creative_service.get_owned_campaign")
    @patch("app.services.creative_service.PexelsImageSearch")
    @patch("app.services.creative_service._get_owned_video_creative")
    @patch("app.services.creative_service.JSON2VideoProvider")
    def test_scene_search_retries_with_simple_query_and_maps_assets_by_scene(
        self, provider_class, get_creative, search_class, get_campaign
    ):
        get_creative.return_value = self.creative
        get_campaign.return_value = Mock(
            name="Launch", product_name="Earbuds", description="Audio", target_audience="Students",
            platform="Instagram", objective="Promotion", tone="Bright", keywords="wireless, commute",
        )
        first_asset = {"image_url": "https://images.example/one.jpg", "source_url": "https://pexels.com/one", "photographer": "A"}
        second_asset = {"image_url": "https://images.example/two.png", "source_url": "https://pexels.com/two", "photographer": "B"}
        search_class.return_value.search.side_effect = [None, first_asset, second_asset]
        provider_class.return_value.create_movie.return_value = {"project_id": "project-assets", "status": "submitted"}

        start_video_render(self.db, 7, 9, 3)

        submitted = provider_class.return_value.create_movie.call_args.kwargs["scene_assets"]
        self.assertEqual([asset["image_url"] for asset in submitted], [first_asset["image_url"], second_asset["image_url"]])
        self.assertTrue(all(asset["fallback"] is None for asset in submitted))
        self.assertEqual(self.creative.generated_content["scene_assets"], submitted)
        self.assertEqual(search_class.return_value.search.call_count, 3)

    @patch("app.services.creative_service.get_owned_campaign")
    @patch("app.services.creative_service.PexelsImageSearch")
    @patch("app.services.creative_service._get_owned_video_creative")
    @patch("app.services.creative_service.JSON2VideoProvider")
    def test_missing_scene_images_fail_before_json2video_submission(
        self, provider_class, get_creative, search_class, get_campaign
    ):
        get_creative.return_value = self.creative
        get_campaign.return_value = Mock(
            name="Launch", product_name="Earbuds", description="Audio", target_audience="Students",
            platform="Instagram", objective="Promotion", tone="Bright", keywords="wireless, commute",
        )
        search_class.return_value.search.return_value = None

        with self.assertRaises(HTTPException) as raised:
            start_video_render(self.db, 7, 9, 3)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("publicly accessible images", raised.exception.detail)
        self.assertEqual(search_class.return_value.search.call_count, 4)
        provider_class.assert_not_called()

    @patch("app.services.creative_service.get_owned_campaign")
    @patch("app.services.creative_service.PexelsImageSearch")
    @patch("app.services.creative_service._get_owned_video_creative")
    @patch("app.services.creative_service.JSON2VideoProvider")
    def test_malformed_image_url_is_retried_then_rejected_before_submission(
        self, provider_class, get_creative, search_class, get_campaign
    ):
        get_creative.return_value = self.creative
        get_campaign.return_value = Mock(
            name="Launch", product_name="Earbuds", description="Audio", target_audience="Students",
            platform="Instagram", objective="Promotion", tone="Bright", keywords="wireless, commute",
        )
        search_class.return_value.search.side_effect = [
            {"image_url": "https://pexels.com/search/earbuds"},
            {"image_url": "https://images.example/first.jpg"},
            {"image_url": "https://images.example/second.jpg"},
        ]
        provider_class.return_value.create_movie.return_value = {"project_id": "project", "status": "submitted"}

        start_video_render(self.db, 7, 9, 3)

        assets = provider_class.return_value.create_movie.call_args.kwargs["scene_assets"]
        self.assertEqual(assets[0]["image_url"], "https://images.example/first.jpg")
        self.assertEqual(assets[1]["image_url"], "https://images.example/second.jpg")

    @patch("app.services.creative_service._get_owned_video_creative")
    @patch("app.services.creative_service.JSON2VideoProvider")
    def test_existing_project_prevents_duplicate_submission(self, provider_class, get_creative):
        self.creative.video_project_id = "project-existing"
        self.creative.video_status = "rendering"
        get_creative.return_value = self.creative

        result = start_video_render(self.db, 7, 9, 3)

        self.assertEqual(result["project_id"], "project-existing")
        provider_class.assert_not_called()
        self.db.commit.assert_not_called()

    @patch("app.services.creative_service._get_owned_video_creative")
    @patch("app.services.creative_service.get_supabase_storage_service")
    @patch("app.services.creative_service.JSON2VideoProvider")
    @patch("app.services.creative_service.httpx.get")
    def test_completed_render_is_uploaded_once(
        self, http_get, provider_class, storage_factory, get_creative
    ):
        self.creative.video_project_id = "14qzRFI9fCdrPMgS"
        self.creative.video_status = "rendering"
        get_creative.return_value = self.creative
        provider_class.return_value.get_movie_status.return_value = {
            "status": "done",
            "result_url": "https://cdn.example/video.mp4",
        }
        response = Mock(content=b"mp4", headers={"content-type": "video/mp4"})
        http_get.return_value = response
        response.raise_for_status.return_value = None
        storage_factory.return_value.upload_video.return_value = "campaigns/7/creatives/9/video.mp4"

        result = update_video_render_status(self.db, 7, 9, 3)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["video_url"], "/api/creative/campaign/7/video/9")
        storage_factory.return_value.upload_video.assert_called_once()
        self.assertEqual(self.creative.video_path, "campaigns/7/creatives/9/video.mp4")
        self.assertEqual(self.creative.video_content_type, "video/mp4")
        self.assertEqual(self.creative.video_result_url, "https://cdn.example/video.mp4")
        self.assertEqual(self.creative.video_status, "completed")
        self.assertEqual(
            self.creative.generated_content["video_render"]["video_url"],
            "https://cdn.example/video.mp4",
        )
        provider_class.return_value.get_movie_status.assert_called_once_with("14qzRFI9fCdrPMgS")
        self.db.add.assert_called()
        self.db.commit.assert_called()

        update_video_render_status(self.db, 7, 9, 3)
        storage_factory.return_value.upload_video.assert_called_once()
        provider_class.return_value.get_movie_status.assert_called_once()
        self.db.commit.assert_called_once()

    def test_provider_error_and_timeout_are_terminal_and_stop_repolling(self):
        self.creative.video_project_id = "project-1"
        self.creative.video_status = "running"
        provider = Mock()
        provider.get_movie_status.return_value = {
            "project_id": "project-1",
            "status": "error",
            "result_url": None,
            "message": "Render failed",
        }
        get_creative = Mock(return_value=self.creative)

        with patch("app.services.creative_service.JSON2VideoProvider", return_value=provider):
            with patch("app.services.creative_service._get_owned_video_creative", get_creative):
                result = update_video_render_status(self.db, 7, 9, 3)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["error"], "Render failed")
                self.assertEqual(self.creative.video_status, "failed")

                result = update_video_render_status(self.db, 7, 9, 3)
                self.assertEqual(result["status"], "failed")
                provider.get_movie_status.assert_called_once_with("project-1")

        self.db.commit.assert_called_once()

    def test_timeout_is_saved_as_failed(self):
        self.creative.video_project_id = "project-1"
        self.creative.video_status = "running"
        provider = Mock()
        provider.get_movie_status.return_value = {
            "project_id": "project-1",
            "status": "timeout",
            "message": "Movie took too long to render",
        }

        with patch("app.services.creative_service.JSON2VideoProvider", return_value=provider):
            with patch("app.services.creative_service._get_owned_video_creative", return_value=self.creative):
                result = update_video_render_status(self.db, 7, 9, 3)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "Movie took too long to render")
        self.assertEqual(self.creative.video_status, "failed")

    @patch("app.services.creative_service._get_owned_video_creative")
    @patch("app.services.creative_service.get_supabase_storage_service")
    @patch("app.services.creative_service.JSON2VideoProvider")
    @patch("app.services.creative_service.httpx.get")
    def test_storage_failure_is_persisted_and_reported(
        self, http_get, provider_class, storage_factory, get_creative
    ):
        self.creative.video_project_id = "project-1"
        self.creative.video_status = "rendering"
        get_creative.return_value = self.creative
        provider_class.return_value.get_movie_status.return_value = {
            "status": "done",
            "result_url": "https://cdn.example/video.mp4",
        }
        response = Mock(content=b"mp4", headers={"content-type": "video/mp4"})
        http_get.return_value = response
        response.raise_for_status.return_value = None
        storage_factory.return_value.upload_video.side_effect = SupabaseStorageError("storage unavailable")

        with self.assertRaises(HTTPException) as raised:
            update_video_render_status(self.db, 7, 9, 3)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("render completed", raised.exception.detail)
        self.assertEqual(self.creative.video_status, "failed")
        self.assertIsNone(self.creative.video_path)
        self.assertEqual(self.creative.video_result_url, "https://cdn.example/video.mp4")
        self.assertEqual(
            self.creative.generated_content["video_render"]["video_url"],
            "https://cdn.example/video.mp4",
        )
        self.db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
