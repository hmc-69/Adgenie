from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Type, TypeVar

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.schemas.audience_analysis import AudienceAnalysisProviderResult
from app.schemas.creative import ImageCreativeBrief, VideoCreativeScript
from app.services.creative.providers.provider import BaseCreativeProvider


ModelT = TypeVar("ModelT", bound=BaseModel)
logger = logging.getLogger(__name__)


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
        api_response_schema: Any | None = None,
    ) -> Dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=api_response_schema or response_schema,
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
        except ValidationError as exc:
            validation_details = [
                {
                    "location": ".".join(str(part) for part in error.get("loc", ())),
                    "message": str(error.get("msg", "Validation failed"))[:240],
                    "type": error.get("type", "unknown"),
                }
                for error in exc.errors(include_url=False)[:20]
            ]
            logger.warning("Gemini structured response schema validation failed: %s", validation_details)
            raise ValueError("Gemini returned invalid structured content") from exc
        except TypeError as exc:
            logger.warning("Gemini structured response could not be parsed as the expected schema")
            raise ValueError("Gemini returned invalid structured content") from exc

    @staticmethod
    def _video_response_schema() -> Dict[str, Any]:
        scene_schema = {
            "type": "OBJECT",
            "properties": {
                "scene_number": {"type": "INTEGER"},
                "duration": {"type": "NUMBER"},
                "visual": {"type": "STRING"},
                "visual_description": {"type": "STRING"},
                "visual_prompt": {"type": "STRING"},
                "voiceover": {"type": "STRING"},
                "on_screen_text": {"type": "STRING"},
            },
            "required": ["scene_number", "duration", "visual", "visual_description", "visual_prompt", "voiceover", "on_screen_text"],
        }
        return {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING"},
                "duration": {"type": "NUMBER"},
                "scenes": {"type": "ARRAY", "items": scene_schema},
                "final_cta": {"type": "STRING"},
            },
            "required": ["title", "duration", "scenes", "final_cta"],
        }

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

    def generate_audience_analysis(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are an advertising audience strategist. Produce practical audience recommendations using
only the campaign information below. Treat all recommendations as hypotheses, not verified facts.
Do not claim to have accessed platform audience data, infer or target sensitive traits, invent
measured demographics or behavioral data, or guarantee campaign performance. Use the supplied
platform when suggesting targeting methods and describe them only as platform-supported options
where available. Explicitly identify assumptions, limitations, and missing information. If inputs
are incomplete, provide cautious recommendations and say what is missing.

Campaign information:
{campaign}

Return a concise audience overview and at least two potential audience segments. Each segment
must include a name, description, relevant interests, needs or pain points, motivations, and a
recommended message angle. Also provide platform-relevant targeting approaches, messaging and
creative considerations, assumptions, limitations, and missing information. Recommendations must
be actionable, truthful, and based only on the provided context.
""".strip()
        return self._generate_structured(prompt, AudienceAnalysisProviderResult)

    def generate_video_script(self, campaign: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are a concise marketing video scriptwriter. Generate a promotional video script of 15 seconds
or less using only
this campaign information:
{campaign}

Match the target audience, campaign objective, platform, and campaign tone. Highlight only the
actual product benefits provided. Avoid invented claims. Start with a strong opening hook,
communicate the product value proposition, and end with a clear call to action.

Generate 2 to 4 scenes for a future AI video-generation system. Use numeric duration values in
seconds (not ranges or strings). The scene durations must add up to exactly the top-level duration
and never exceed 15 seconds. Keep voiceovers short enough to be spoken within their scene timing,
provide a concise visual_description for each scene describing a photograph to search for (include
the subject, setting, and useful visual details). The visual_description is metadata only and must
never be used as on-screen text. Also provide a visual_prompt for an image-generation model that
describes the scene composition, product context, environment, and lighting. Do not include
narration, captions, written words, or logos in this prompt. Preserve the scene's visual direction, narration, and caption;
avoid excessive on-screen text, and include a short, clear call to action in the final scene's
voiceover and on-screen text. Set top-level final_cta to exactly the final scene's on_screen_text,
character for character. The top-level duration must be the numeric sum of all scene durations.
Do not generate the actual video.
""".strip()
        try:
            return self._generate_structured(
                prompt,
                VideoCreativeScript,
                self._video_response_schema(),
            )
        except ValueError as exc:
            retry_prompt = f"""
The previous video script was invalid. Regenerate it strictly as a concise advertising script
using only this campaign information:
{campaign}

Return exactly 2 to 4 scenes. Every scene duration must be a positive number of seconds. The
top-level duration must equal the sum of all scene durations and that sum must be no greater than
15 seconds. Include a concise photo-search visual_description and contextual visual_prompt in
every scene; do not put either on screen. Keep every voiceover brief enough for its scene, use minimal on-screen text, and put a
short call to action in the final scene's voiceover and on-screen text. The top-level final_cta
must exactly match the final scene's on_screen_text, character for character. Return JSON matching
the requested schema only.
""".strip()
            try:
                return self._generate_structured(
                    retry_prompt,
                    VideoCreativeScript,
                    self._video_response_schema(),
                )
            except ValueError as retry_exc:
                raise ValueError("Gemini returned an invalid video script after one retry") from retry_exc

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
