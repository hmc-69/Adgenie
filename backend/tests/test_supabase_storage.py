import unittest
from unittest.mock import Mock, patch

from app.services.storage.supabase_storage import (
    SupabaseStorageError,
    SupabaseStorageNotFoundError,
    SupabaseStorageService,
)


class SupabaseStorageTests(unittest.TestCase):
    def setUp(self):
        self.service = SupabaseStorageService()
        self.bucket = Mock()
        self.storage = Mock()
        self.storage.from_.return_value = self.bucket
        self.client = Mock()
        self.client.storage = self.storage
        self.service._client = self.client

    def test_upload_uses_private_predictable_object_path(self):
        with patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_STORAGE_BUCKET",
            "adgenie-images",
        ):
            path = self.service.upload_image(b"image-bytes", "image/png", 4, 9)

        self.assertRegex(path, r"^campaigns/4/creatives/9/[0-9a-f]{32}\.png$")
        self.storage.from_.assert_called_once_with("adgenie-images")
        self.bucket.upload.assert_called_once()
        self.assertEqual(self.bucket.upload.call_args.args[1], b"image-bytes")
        self.assertEqual(
            self.bucket.upload.call_args.kwargs["file_options"]["content-type"],
            "image/png",
        )

    def test_download_returns_image_bytes(self):
        self.bucket.download.return_value = b"image-bytes"
        with patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_STORAGE_BUCKET",
            "adgenie-images",
        ):
            result = self.service.download_image("campaigns/4/creatives/9/image.jpg")

        self.assertEqual(result, b"image-bytes")

    def test_video_scene_upload_uses_unique_private_path_and_actual_format(self):
        with patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_STORAGE_BUCKET",
            "adgenie-images",
        ):
            path = self.service.upload_video_scene_image(b"webp-bytes", "image/webp", 4, 9, 2)

        self.assertRegex(path, r"^campaigns/4/video-scenes/9/scene-2-[0-9a-f]{32}\.webp$")
        options = self.bucket.upload.call_args.kwargs["file_options"]
        self.assertEqual(options["content-type"], "image/webp")
        self.assertEqual(options["upsert"], False)
        self.assertTrue(options["cache-control"].startswith("private"))

    def test_signed_scene_url_uses_existing_private_bucket_and_expiry(self):
        self.bucket.create_signed_url.return_value = {
            "signedURL": "https://storage.example/private-image.jpg?token=temporary",
            "signedUrl": "https://storage.example/private-image.jpg?token=temporary",
        }
        with patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_STORAGE_BUCKET",
            "adgenie-images",
        ):
            url = self.service.create_signed_image_url("campaigns/4/video-scenes/9/scene.jpg", 21600)

        self.assertEqual(url, "https://storage.example/private-image.jpg?token=temporary")
        self.storage.from_.assert_called_once_with("adgenie-images")
        self.bucket.create_signed_url.assert_called_once_with("campaigns/4/video-scenes/9/scene.jpg", 21600)

    def test_download_maps_missing_object_to_not_found(self):
        self.bucket.download.side_effect = RuntimeError("404 not found")
        with patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_STORAGE_BUCKET",
            "adgenie-images",
        ):
            with self.assertRaises(SupabaseStorageNotFoundError):
                self.service.download_image("campaigns/4/creatives/9/missing.jpg")

    def test_publishable_key_is_rejected_before_client_creation(self):
        service = SupabaseStorageService()
        with patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_URL",
            "https://example.supabase.co",
        ), patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_SERVICE_ROLE_KEY",
            "sb_publishable_test",
        ), patch(
            "app.services.storage.supabase_storage.settings.SUPABASE_STORAGE_BUCKET",
            "generated_ad",
        ):
            with self.assertRaises(SupabaseStorageError):
                service._get_client()


if __name__ == "__main__":
    unittest.main()
