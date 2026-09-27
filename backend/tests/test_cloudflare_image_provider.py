import json
from io import BytesIO
import unittest
from email.message import Message
from urllib.error import HTTPError
from unittest.mock import Mock, patch

from app.services.creative.providers.cloudflare_image_provider import (
    CloudflareImageProvider,
    CloudflareImageProviderError,
)
from app.services.creative.text_generator import get_image_provider
from app.core.config import settings


class CloudflareImageProviderTests(unittest.TestCase):
    def _response(self, content_type="image/jpeg", content=b"jpeg-image"):
        response = Mock()
        response.headers = Message()
        response.headers["Content-Type"] = content_type
        response.read.return_value = content
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def test_sends_worker_contract_and_normalizes_jpeg_bytes(self):
        response = self._response()
        with patch("app.services.creative.providers.cloudflare_image_provider.urlopen", return_value=response) as urlopen:
            with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_IMAGE_API_URL", "https://worker.example/"):
                with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_API_KEY", "test-secret"):
                    result = CloudflareImageProvider().generate_image("A polished campaign ad", "4:5")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(request.get_header("Accept"), "image/jpeg")
        self.assertEqual(request.get_header("User-agent"), "AdGenie/1.0")
        self.assertEqual(
            json.loads(request.data),
            {"prompt": "A polished campaign ad", "aspect_ratio": "4:5"},
        )
        self.assertEqual(result.content, b"jpeg-image")
        self.assertEqual(result.content_type, "image/jpeg")

    def test_rejects_non_image_worker_responses(self):
        response = self._response("application/json", b'{"error":"Failed"}')
        with patch("app.services.creative.providers.cloudflare_image_provider.urlopen", return_value=response):
            with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_IMAGE_API_URL", "https://worker.example/"):
                with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_API_KEY", "test-secret"):
                    with self.assertRaises(CloudflareImageProviderError):
                        CloudflareImageProvider().generate_image("A campaign ad")

    def test_rejects_unsupported_aspect_ratio_before_request(self):
        with patch("app.services.creative.providers.cloudflare_image_provider.urlopen") as urlopen:
            with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_IMAGE_API_URL", "https://worker.example/"):
                with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_API_KEY", "test-secret"):
                    with self.assertRaisesRegex(ValueError, "Unsupported aspect ratio"):
                        CloudflareImageProvider().generate_image("A campaign ad", "2:1")

        urlopen.assert_not_called()

    def test_http_error_logs_sanitized_worker_message(self):
        for status_code in (401, 403, 500):
            with self.subTest(status_code=status_code):
                error = HTTPError(
                    "https://worker.example/",
                    status_code,
                    "Forbidden",
                    {},
                    BytesIO(b'{"error":"Forbidden: Bearer test-secret rejected"}'),
                )
                with patch("app.services.creative.providers.cloudflare_image_provider.urlopen", side_effect=error):
                    with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_IMAGE_API_URL", "https://worker.example/"):
                        with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_API_KEY", "test-secret"):
                            with self.assertLogs(
                                "app.services.creative.providers.cloudflare_image_provider",
                                level="WARNING",
                            ) as captured:
                                with self.assertRaisesRegex(
                                    CloudflareImageProviderError,
                                    f"HTTP {status_code}",
                                ):
                                    CloudflareImageProvider().generate_image("A campaign ad")

                self.assertIn(f"status={status_code}", captured.output[0])
                self.assertIn("Forbidden", captured.output[0])
                self.assertNotIn("test-secret", captured.output[0])

    def test_html_edge_error_logs_title_instead_of_markup(self):
        headers = Message()
        headers["Content-Type"] = "text/html"
        error = HTTPError(
            "https://worker.example/",
            403,
            "Forbidden",
            headers,
            BytesIO(b"<html><head><title>Access denied</title></head><body>edge page</body></html>"),
        )
        with patch("app.services.creative.providers.cloudflare_image_provider.urlopen", side_effect=error):
            with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_IMAGE_API_URL", "https://worker.example/"):
                with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_API_KEY", "test-secret"):
                    with self.assertLogs(
                        "app.services.creative.providers.cloudflare_image_provider",
                        level="WARNING",
                    ) as captured:
                        with self.assertRaises(CloudflareImageProviderError):
                            CloudflareImageProvider().generate_image("A campaign ad")

        self.assertIn("status=403", captured.output[0])
        self.assertIn("Access denied", captured.output[0])
        self.assertIn("response_body='<html>", captured.output[0])

    def test_http_error_logs_only_selected_headers_and_redacted_body_prefix(self):
        headers = Message()
        headers["Content-Type"] = "text/plain"
        headers["CF-Mitigated"] = "challenge"
        headers["CF-Ray"] = "ray-id"
        headers["Server"] = "cloudflare"
        headers["Set-Cookie"] = "session=must-not-log"
        response_body = "Sensitive prompt content " + ("x" * 350)
        error = HTTPError(
            "https://worker.example/",
            403,
            "Forbidden",
            headers,
            BytesIO(response_body.encode("utf-8")),
        )
        with patch("app.services.creative.providers.cloudflare_image_provider.urlopen", side_effect=error):
            with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_IMAGE_API_URL", "https://worker.example/"):
                with patch("app.services.creative.providers.cloudflare_image_provider.settings.CLOUDFLARE_API_KEY", "test-secret"):
                    with self.assertLogs(
                        "app.services.creative.providers.cloudflare_image_provider",
                        level="WARNING",
                    ) as captured:
                        with self.assertRaises(CloudflareImageProviderError):
                            CloudflareImageProvider().generate_image(
                                "Sensitive prompt content", "4:5"
                            )

        log = captured.output[0]
        self.assertIn("status=403", log)
        self.assertIn("content-type", log)
        self.assertIn("cf-mitigated", log)
        self.assertIn("cf-ray", log)
        self.assertIn("server", log)
        self.assertIn("[PROMPT REDACTED]", log)
        self.assertNotIn("Sensitive prompt content", log)
        self.assertNotIn("session=must-not-log", log)
        self.assertNotIn("test-secret", log)
        logged_body = log.split("response_body=", 1)[1]
        self.assertLessEqual(len(logged_body.strip("'")), 300)

    def test_image_provider_selection_is_independent_from_text_provider(self):
        with patch.object(settings, "AI_PROVIDER", "gemini"), patch.object(
            settings, "IMAGE_PROVIDER", "cloudflare"
        ), patch.object(settings, "CLOUDFLARE_IMAGE_API_URL", "https://worker.example/"), patch.object(
            settings, "CLOUDFLARE_API_KEY", "test-secret"
        ):
            provider = get_image_provider()

        self.assertIsInstance(provider, CloudflareImageProvider)


if __name__ == "__main__":
    unittest.main()