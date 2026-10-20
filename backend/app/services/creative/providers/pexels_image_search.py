from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)
PEXELS_API_URL = "https://api.pexels.com/v1/search"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_IMAGE_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}


class PexelsImageSearch:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=httpx.Timeout(12.0, connect=5.0), follow_redirects=True)

    @staticmethod
    def parse_photo_results(data: Any) -> dict[str, Any] | None:
        if not isinstance(data, dict) or not isinstance(data.get("photos"), list):
            return None
        photos = [photo for photo in data["photos"] if isinstance(photo, dict)]
        # Prefer the largest landscape result, but accept a smaller image when the result set
        # contains no full-HD source.
        photos.sort(key=lambda photo: int(photo.get("width") or 0) * int(photo.get("height") or 0), reverse=True)
        for photo in photos:
            src = photo.get("src") if isinstance(photo.get("src"), dict) else {}
            image_url = src.get("landscape") or src.get("large2x") or src.get("large")
            if not _is_public_http_url(image_url):
                continue
            if not str(image_url).lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                continue
            return {
                "image_url": image_url,
                "source_url": photo.get("url") if _is_public_http_url(photo.get("url")) else None,
                "photographer": str(photo.get("photographer") or "").strip() or None,
                "photographer_url": photo.get("photographer_url") if _is_public_http_url(photo.get("photographer_url")) else None,
                "width": photo.get("width"),
                "height": photo.get("height"),
                "provider": "pexels",
            }
        return None

    def _validated_asset(self, image: dict[str, Any]) -> dict[str, Any] | None:
        try:
            # Fetch just the beginning of the public asset. This checks that the URL can be
            # fetched without credentials and that the response body is actually an image.
            response = self._client.get(image["image_url"], headers={"Range": "bytes=0-31"})
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].lower()
            if content_type not in _SUPPORTED_IMAGE_TYPES:
                logger.warning("Pexels image URL returned unsupported content type: %s", content_type or "missing")
                return None
            prefix = response.content[:32]
            signatures = _IMAGE_SIGNATURES[content_type]
            is_valid_signature = (
                prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"
                if content_type == "image/webp"
                else any(prefix.startswith(signature) for signature in signatures)
            )
            if not is_valid_signature:
                logger.warning("Pexels image URL did not return a valid %s file", content_type)
                return None
            return image
        except (httpx.HTTPError, KeyError) as exc:
            logger.warning("Pexels image URL could not be verified: %s", exc)
            return None

    def search(self, visual_description: str, campaign: Dict[str, Any]) -> dict[str, Any] | None:
        if not settings.PEXELS_API_KEY:
            logger.warning("Image retrieval unavailable: PEXELS_API_KEY is not configured")
            return None
        product = str(campaign.get("product_name") or "").strip()
        keywords = str(campaign.get("keywords") or "").strip()
        query = " ".join(part for part in (visual_description.strip(), product, keywords) if part)
        query = re.sub(r"\s+", " ", query)[:240]
        cache_key = query.casefold()
        cached = _CACHE.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        try:
            response = self._client.get(
                PEXELS_API_URL,
                params={"query": query, "orientation": "landscape", "size": "large", "per_page": 10},
                headers={"Authorization": settings.PEXELS_API_KEY},
            )
            response.raise_for_status()
            image = self.parse_photo_results(response.json())
            image = self._validated_asset(image) if image else None
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Pexels photo search failed: %s", exc)
            image = None
        if image is not None:
            _CACHE[cache_key] = (time.monotonic() + _CACHE_TTL_SECONDS, image)
        else:
            _CACHE.pop(cache_key, None)
        return image


def _is_public_http_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password
    except ValueError:
        return False
