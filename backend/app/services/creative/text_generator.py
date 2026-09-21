from __future__ import annotations

from typing import Any, Dict

from app.core.config import settings
from app.services.creative.providers.gemini_provider import GeminiCreativeProvider
from app.services.creative.providers.mock_provider import MockCreativeProvider
from app.services.creative.providers.provider import BaseCreativeProvider


def get_provider() -> BaseCreativeProvider:
    provider_name = settings.AI_PROVIDER
    if provider_name == "mock":
        return MockCreativeProvider()
    if provider_name == "gemini":
        return GeminiCreativeProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {provider_name}")


def generate_image_brief(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return get_provider().generate_image_brief(campaign)


def generate_video_script(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return get_provider().generate_video_script(campaign)
