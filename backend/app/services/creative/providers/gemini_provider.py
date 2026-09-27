from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Type, TypeVar

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.schemas.creative import ImageCreativeBrief, VideoCreativeScript
from app.services.creative.providers.provider import BaseCreativeProvider


ModelT = TypeVar("ModelT", bound=BaseModel)


class GeminiCreativeProvider(BaseCreativeProvider):
    def __init__(self) -> None:
        if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your_key_here":
            raise ValueError("GEMINI_API_KEY is not configured")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL
        self.image_model = settings.GEMINI_IMAGE_MODEL

    def _generate_structured(
        self,
        prompt: str,
        response_schema: Type[ModelT],
    ) -> Dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
        parsed = getattr(response, "parsed", None)
        if parsed is None:
            raise ValueError("Gemini returned no structured content")
        try:
            return response_schema.model_validate(parsed).model_dump()
        except (TypeError, ValidationError) as exc:
            raise ValueError("Gemini returned invalid structured content") from exc

    def generate_image_brief(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are an advertising creative strategist. Create an advertising creative brief using only
this campaign information:
{campaign}

The advertisement must match the target audience, selected platform, campaign objective, and
selected tone. Naturally incorporate relevant keywords. Write compelling but truthful marketing
copy. Do not invent product features or make unsupported claims. Keep the copy concise and usable.

Generate a headline, primary text, description, call to action, hashtags, and visual direction.
Visual direction should describe what a future image-generation model should create; do not
attempt to generate the image itself.
""".strip()
        return self._generate_structured(prompt, ImageCreativeBrief)

    def generate_video_script(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are a marketing video scriptwriter. Generate a short promotional video script using only
this campaign information:
{campaign}

Match the target audience, campaign objective, platform, and campaign tone. Highlight only the
actual product benefits provided. Avoid invented claims. Start with a strong opening hook,
communicate the product value proposition, and end with a clear call to action.

Generate multiple scenes for a future AI video-generation system. Each scene must include a scene
number, duration, visual direction, voiceover, and on-screen text. Do not generate the actual video.
""".strip()
        return self._generate_structured(prompt, VideoCreativeScript)

    def generate_advertisement_image(
        self,
        campaign: Dict[str, Any],
        creative: Dict[str, Any],
        aspect_ratio: str,
        style: str,
        resolution: str | None = None,
    ) -> bytes:
        if aspect_ratio not in {"1:1", "4:5", "9:16", "16:9", "3:4"}:
            raise ValueError("Unsupported aspect ratio")

        from app.services.creative.text_generator import build_image_generation_prompt

        prompt = build_image_generation_prompt(campaign, creative, aspect_ratio, style, resolution)
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        )
        try:
            response = self.client.models.generate_content(
                model=self.image_model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            if (
                isinstance(exc, ClientError)
                and exc.code in {400, 404}
                and ("model" in str(exc).lower() or "unsupported" in str(exc).lower())
            ):
                raise ValueError(f"Unsupported Gemini image model: {self.image_model}") from exc
            raise

        try:
            candidates = getattr(response, "candidates", None) or []
            parts = getattr(candidates[0].content, "parts", []) if candidates else []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data and getattr(inline_data, "data", None):
                    return inline_data.data
        except Exception as exc:
            raise ValueError("Gemini returned an invalid image response") from exc

        raise ValueError("Gemini returned no image bytes in the response")

    def get_supported_resolutions(self) -> list[str]:
        from app.services.creative.text_generator import get_supported_image_resolutions

        return get_supported_image_resolutions(self.image_model)


def save_generated_image_bytes(image_bytes: bytes, campaign_id: int, original_creative_id: int, aspect_ratio: str, style: str, resolution: str | None = None) -> tuple[str, str]:
    from app.database import Base

    output_dir = Path("generated_images")
    output_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"adgenie-campaign-{campaign_id}-creative-{original_creative_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.png"
    file_path = output_dir / file_name
    file_path.write_bytes(image_bytes)
    relative_url = f"/generated-images/{file_name}"
    return relative_url, str(file_path)
