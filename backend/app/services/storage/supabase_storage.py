from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urlsplit

from supabase import create_client

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class SupabaseStorageError(RuntimeError):
    """Raised when Supabase Storage cannot complete an operation."""


class SupabaseStorageNotFoundError(SupabaseStorageError):
    """Raised when a requested Supabase Storage object does not exist."""


class SupabaseStorageService:
    def __init__(self) -> None:
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise SupabaseStorageError("Supabase Storage is not configured")
        if not settings.SUPABASE_STORAGE_BUCKET:
            raise SupabaseStorageError("Supabase Storage bucket is not configured")

        url_host = urlsplit(settings.SUPABASE_URL).hostname or "[invalid-url]"
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        key_kind = _get_key_kind(key)
        logger.info("Supabase URL host: %s", url_host)
        logger.info("Supabase bucket: %s", settings.SUPABASE_STORAGE_BUCKET)
        logger.info("Supabase service-role key loaded: %s", bool(key))
        logger.info("Supabase service-role key length: %s", len(key) if key else 0)
        logger.info("Supabase key type detected: %s", key_kind)
        if key_kind == "publishable":
            raise SupabaseStorageError(
                "Supabase Storage requires SUPABASE_SERVICE_ROLE_KEY; a publishable key was configured"
            )

        try:
            self._client = create_client(
                settings.SUPABASE_URL,
                key,
            )
            return self._client
        except Exception as exc:
            raise SupabaseStorageError("Supabase Storage initialization failed") from exc

    def upload_image(
        self,
        image_bytes: bytes,
        content_type: str,
        campaign_id: int,
        creative_id: int,
    ) -> str:
        extension = IMAGE_EXTENSIONS.get(content_type)
        if extension is None:
            raise SupabaseStorageError("Unsupported generated image format")

        storage_path = (
            f"campaigns/{campaign_id}/creatives/{creative_id}/"
            f"{uuid.uuid4().hex}{extension}"
        )
        try:
            self._get_client().storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
                storage_path,
                image_bytes,
                file_options={
                    "content-type": content_type,
                    "cache-control": "public,max-age=31536000,immutable",
                    "upsert": False,
                },
            )
            return storage_path
        except SupabaseStorageError:
            raise
        except Exception as exc:
            raise SupabaseStorageError("Supabase image upload failed") from exc

    def download_image(self, storage_path: str) -> bytes:
        try:
            return self._get_client().storage.from_(
                settings.SUPABASE_STORAGE_BUCKET
            ).download(storage_path)
        except SupabaseStorageError:
            raise
        except Exception as exc:
            if "not found" in str(exc).lower() or "404" in str(exc):
                raise SupabaseStorageNotFoundError("Stored image does not exist") from exc
            raise SupabaseStorageError("Supabase image retrieval failed") from exc

    def delete_image(self, storage_path: str) -> None:
        try:
            self._get_client().storage.from_(
                settings.SUPABASE_STORAGE_BUCKET
            ).remove([storage_path])
        except SupabaseStorageError:
            raise
        except Exception as exc:
            raise SupabaseStorageError("Supabase image deletion failed") from exc


_supabase_storage_service = SupabaseStorageService()


def get_supabase_storage_service() -> SupabaseStorageService:
    return _supabase_storage_service


def _get_key_kind(key: str | None) -> str:
    if not key:
        return "missing"
    if key.startswith("sb_publishable_"):
        return "publishable"
    if key.startswith("sb_secret_") or key.startswith("eyJ"):
        return "service-role-or-secret"
    return "unknown"
