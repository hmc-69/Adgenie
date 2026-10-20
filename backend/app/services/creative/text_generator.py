from __future__ import annotations

import logging
from typing import Any, Dict

from google.genai.errors import ServerError

from app.core.config import settings
from app.schemas.creative import VideoCreativeScript
from app.services.creative.providers.gemini_provider import GeminiCreativeProvider
from app.services.creative.providers.cloudflare_image_provider import CloudflareImageProvider
from app.services.creative.providers.mock_provider import MockCreativeProvider
from app.services.creative.providers.provider import BaseCreativeProvider


logger = logging.getLogger(__name__)


def get_provider() -> BaseCreativeProvider:
    provider_name = settings.AI_PROVIDER
    if provider_name == "mock":
        return MockCreativeProvider()
    if provider_name == "gemini":
        return GeminiCreativeProvider()
    raise ValueError(f"Unsupported AI_PROVIDER: {provider_name}")


def get_image_provider() -> CloudflareImageProvider:
    provider_name = settings.IMAGE_PROVIDER
    if provider_name == "cloudflare":
        return CloudflareImageProvider()
    raise ValueError(f"Unsupported IMAGE_PROVIDER: {provider_name}")


def build_image_generation_prompt(
    campaign: Dict[str, Any],
    creative: Dict[str, Any],
    aspect_ratio: str,
    style: str,
    resolution: str | None = None,
) -> str:
    campaign_name = str(campaign.get("name") or "Campaign")
    product_name = str(campaign.get("product_name") or "Product")
    product_description = str(campaign.get("description") or "")
    audience = str(campaign.get("target_audience") or "")
    platform = str(campaign.get("platform") or "")
    objective = str(campaign.get("objective") or "")
    tone = str(campaign.get("tone") or "")
    keywords = campaign.get("keywords") or ""
    if isinstance(keywords, list):
        keywords = ", ".join(str(item) for item in keywords)

    headline = str(creative.get("headline") or "")
    primary_text = str(creative.get("primary_text") or "")
    description = str(creative.get("description") or "")
    cta = str(creative.get("call_to_action") or "")
    hashtags = creative.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = [hashtags]
    visual_direction = str(creative.get("visual_direction") or "")

    style_label = str(style or "AI Recommended")
    ratio_label = str(aspect_ratio or "1:1")
    style_directions = {
        "AI Recommended": "Choose the visual treatment best suited to the campaign and audience.",
        "Photographic": "Use natural, believable photography, refined lighting, and realistic materials.",
        "Minimal": "Use generous negative space, a restrained palette, and only essential elements.",
        "Editorial": "Use art-directed editorial composition, considered typography, and magazine-quality imagery.",
        "Bold Graphic": "Use confident graphic shapes, crisp contrast, and energetic visual hierarchy.",
        "Luxury": "Use premium materials, polished lighting, elegant restraint, and sophisticated detail.",
        "Playful": "Use upbeat color, expressive composition, and approachable, lively details.",
    }
    style_direction = style_directions.get(style_label, style_directions["AI Recommended"])

    prompt = f"""
Create a polished marketing advertisement for {campaign_name} promoting {product_name}.
Campaign context:
- Product: {product_name}
- Description: {product_description}
- Target audience: {audience}
- Platform: {platform}
- Objective: {objective}
- Tone: {tone}
- Keywords: {keywords}

Creative brief to reuse:
- Headline: {headline}
- Primary text: {primary_text}
- Description: {description}
- CTA: {cta}
- Hashtags: {', '.join(str(item) for item in hashtags if str(item).strip()) or 'None'}
- Visual direction: {visual_direction}

Image settings:
- Aspect ratio: {ratio_label}
- Visual style: {style_label}
- Style direction: {style_direction}
{f'- Requested resolution: {resolution}' if resolution else ''}

Requirements:
- Produce a premium advertising image that matches the selected aspect ratio and visual style.
- Preserve the campaign/product context, brand tone, and visual direction while creating a clean, high-impact ad layout.
- Use a compelling composition with a strong focal product or lifestyle scene.
- Include the provided headline and call to action as legible advertising text when the composition supports it; preserve their wording.
- Reserve clear space for marketing text and avoid unnecessary clutter.
- Maintain professional visual hierarchy and polished marketing aesthetics.
- Keep the result suitable for {platform} and aligned to the campaign objective.
""".strip()
    return prompt


def generate_image_brief(campaign: Dict[str, Any]) -> Dict[str, Any]:
    provider = get_provider()
    try:
        return provider.generate_image_brief(campaign)
    except ServerError as exc:
        if (
            settings.AI_PROVIDER == "gemini"
            and settings.AI_FALLBACK_TO_MOCK
            and exc.code in {500, 502, 503, 504}
        ):
            logger.warning(
                "Gemini image brief generation returned %s; using mock fallback",
                exc.code,
            )
            return MockCreativeProvider().generate_image_brief(campaign)
        raise


def generate_video_script(campaign: Dict[str, Any]) -> Dict[str, Any]:
    result = get_provider().generate_video_script(campaign)
    return VideoCreativeScript.model_validate(result).model_dump()


def get_supported_image_resolutions(model_name: str | None = None) -> list[str]:
    configured_model = (model_name or settings.GEMINI_IMAGE_MODEL or "").strip()
    if not configured_model:
        return ["1K"]
    lower_name = configured_model.lower()
    if "imagen" in lower_name or "imagegeneration" in lower_name:
        return ["1K", "2K", "4K"]
    if "flash-image" in lower_name or "gemini-2.5-flash-image" in lower_name:
        return ["1K"]
    return ["1K"]
