from __future__ import annotations

import os
from typing import Any, Dict

from app.services.creative.providers.mock_provider import MockCreativeProvider
from app.services.creative.providers.provider import BaseCreativeProvider


def get_provider() -> BaseCreativeProvider:
    provider_name = os.getenv("AI_PROVIDER", "mock").lower()
    if provider_name == "mock":
        return MockCreativeProvider()
    return MockCreativeProvider()


def generate_image_brief(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return get_provider().generate_image_brief(campaign)


def generate_video_script(campaign: Dict[str, Any]) -> Dict[str, Any]:
    return get_provider().generate_video_script(campaign)
