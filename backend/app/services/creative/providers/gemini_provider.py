from __future__ import annotations

from typing import Any, Dict, Type, TypeVar

from google import genai
from google.genai import types
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
