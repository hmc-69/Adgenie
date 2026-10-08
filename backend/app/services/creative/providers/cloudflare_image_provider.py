from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from app.core.config import settings


logger = logging.getLogger(__name__)


def _redact_diagnostic_value(value: str, api_key: str, prompt: str) -> str:
    if api_key:
        value = value.replace(api_key, "[REDACTED]")
    if prompt:
        value = value.replace(prompt, "[PROMPT REDACTED]")
    value = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [REDACTED]", value)
    return re.sub(
        r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        "[JWT REDACTED]",
        value,
    )


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    content_type: str


class CloudflareImageProviderError(RuntimeError):
    pass


class CloudflareImageProvider:
    def __init__(self) -> None:
        if not settings.CLOUDFLARE_IMAGE_API_URL or not settings.CLOUDFLARE_API_KEY:
            raise ValueError("Cloudflare image provider is not configured")
        self.api_url = settings.CLOUDFLARE_IMAGE_API_URL
        self.api_key = settings.CLOUDFLARE_API_KEY

    def generate_image(self, prompt: str, aspect_ratio: str = "1:1") -> GeneratedImage:
        if not prompt.strip():
            raise ValueError("Image prompt cannot be empty")
        if aspect_ratio not in {"1:1", "4:5", "9:16", "16:9", "3:4"}:
            raise ValueError("Unsupported aspect ratio")

        request = Request(
            self.api_url,
            data=json.dumps({"prompt": prompt, "aspect_ratio": aspect_ratio}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "image/jpeg",
                "User-Agent": "AdGenie/1.0",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=120) as response:
                content_type = response.headers.get_content_type().lower()
                image_bytes = response.read()
        except HTTPError as exc:
            try:
                error_body = exc.read(4096).decode("utf-8", errors="replace")
            finally:
                exc.close()
            safe_headers = {}
            for header_name in ("content-type", "cf-mitigated", "cf-ray", "server"):
                value = exc.headers.get(header_name, "") if exc.headers else ""
                safe_headers[header_name] = _redact_diagnostic_value(
                    str(value), self.api_key, prompt
                )
            safe_body = _redact_diagnostic_value(
                error_body, self.api_key, prompt
            )[:300]
            logger.warning(
                "Cloudflare HTTP error status=%s response_headers=%s response_body=%r",
                exc.code,
                safe_headers,
                safe_body,
            )
            raise CloudflareImageProviderError(
                f"Cloudflare Worker returned HTTP {exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", None)
            error_code = getattr(reason, "winerror", None) or getattr(reason, "errno", None)
            logger.warning(
                "Cloudflare Worker connection failed host=%s exception=%s error_code=%s",
                urlsplit(self.api_url).hostname or "[invalid-url]",
                type(exc).__name__,
                error_code,
            )
            raise CloudflareImageProviderError("Cloudflare Worker is unavailable") from exc

        if content_type not in {"image/jpeg", "image/png", "image/webp"} or not image_bytes:
            raise CloudflareImageProviderError("Cloudflare Worker returned an unsupported image response")

        return GeneratedImage(content=image_bytes, content_type=content_type)