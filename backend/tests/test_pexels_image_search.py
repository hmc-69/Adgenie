import unittest
from unittest.mock import Mock, patch

import httpx

from app.core.config import settings
from app.services.creative.providers.pexels_image_search import PexelsImageSearch


def pexels_result(image_url="https://images.pexels.com/photos/1/photo.jpeg"):
    return {
        "photos": [
            {
                "width": 1920,
                "height": 1080,
                "url": "https://www.pexels.com/photo/example/",
                "photographer": "Example Photographer",
                "photographer_url": "https://www.pexels.com/@example/",
                "src": {"landscape": image_url, "large": "https://images.pexels.com/photos/1/large.jpeg"},
            }
        ]
    }


class PexelsImageSearchTests(unittest.TestCase):
    def test_parses_direct_landscape_url_and_attribution(self):
        result = PexelsImageSearch.parse_photo_results(pexels_result())
        self.assertEqual(result["image_url"], "https://images.pexels.com/photos/1/photo.jpeg")
        self.assertEqual(result["source_url"], "https://www.pexels.com/photo/example/")
        self.assertEqual(result["photographer"], "Example Photographer")

    def test_rejects_missing_or_non_image_urls(self):
        self.assertIsNone(PexelsImageSearch.parse_photo_results({"photos": []}))
        self.assertIsNone(PexelsImageSearch.parse_photo_results(pexels_result("https://pexels.com/search/photo/")))

    def test_search_uses_campaign_details_and_landscape_preference(self):
        client = Mock()
        search_response = Mock()
        search_response.json.return_value = pexels_result()
        search_response.raise_for_status.return_value = None
        asset_response = Mock(status_code=206, headers={"content-type": "image/jpeg"}, content=b"\xff\xd8\xff" + b"0" * 29)
        asset_response.raise_for_status.return_value = None
        client.get.side_effect = [search_response, asset_response]
        with patch.object(settings, "PEXELS_API_KEY", "test-key"):
            result = PexelsImageSearch(client=client).search(
                "Student wearing earbuds on commute",
                {"product_name": "Wireless earbuds", "keywords": "student audio"},
            )
        self.assertIsNotNone(result)
        kwargs = client.get.call_args_list[0].kwargs
        self.assertEqual(kwargs["params"]["orientation"], "landscape")
        self.assertIn("Wireless earbuds", kwargs["params"]["query"])
        self.assertEqual(kwargs["headers"]["Authorization"], "test-key")
        self.assertEqual(client.get.call_args_list[1].kwargs["headers"], {"Range": "bytes=0-31"})

    def test_unreachable_or_unsupported_asset_returns_none(self):
        client = Mock()
        search_response = Mock()
        search_response.json.return_value = pexels_result()
        search_response.raise_for_status.return_value = None
        invalid_response = Mock(status_code=200, headers={"content-type": "text/html"}, content=b"not an image")
        invalid_response.raise_for_status.return_value = None
        client.get.side_effect = [search_response, invalid_response]
        with patch.object(settings, "PEXELS_API_KEY", "test-key"):
            self.assertIsNone(PexelsImageSearch(client=client).search("Product outdoors", {}))

        client.reset_mock()
        client.get.side_effect = [search_response, httpx.ConnectError("offline")]
        with patch.object(settings, "PEXELS_API_KEY", "test-key"):
            self.assertIsNone(PexelsImageSearch(client=client).search("Another product scene", {}))

    def test_missing_key_skips_external_request(self):
        client = Mock()
        with patch.object(settings, "PEXELS_API_KEY", None):
            self.assertIsNone(PexelsImageSearch(client=client).search("Product scene", {}))
        client.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
