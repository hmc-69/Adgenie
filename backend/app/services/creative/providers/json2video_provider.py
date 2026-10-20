from __future__ import annotations

from typing import Any, Dict
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.schemas.creative import VideoCreativeScript

DEFAULT_VOICE_ID = "en-GB-RyanNeural"
VOICE_MODEL = "azure"


class JSON2VideoError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class JSON2VideoProvider:
    def __init__(self, client: httpx.Client | None = None) -> None:
        if not settings.JSON2VIDEO_API_KEY:
            raise JSON2VideoError("JSON2VIDEO_API_KEY is not configured")
        self._client = client or httpx.Client(
            base_url=settings.JSON2VIDEO_API_URL,
            headers={"x-api-key": settings.JSON2VIDEO_API_KEY},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    @staticmethod
    def build_movie_payload(
        script: Dict[str, Any],
        image_urls: list[str] | None = None,
        scene_assets: list[Dict[str, Any] | None] | None = None,
    ) -> Dict[str, Any]:
        validated = VideoCreativeScript.model_validate(script)
        scenes = []
        for index, scene in enumerate(validated.scenes):
            asset = scene_assets[index] if scene_assets and index < len(scene_assets) else None
            image_url = asset.get("image_url") if isinstance(asset, dict) else None
            if not image_url and image_urls and index < len(image_urls):
                image_url = image_urls[index]
            parsed_image_url = urlparse(image_url) if isinstance(image_url, str) else None
            if (
                parsed_image_url is None
                or parsed_image_url.scheme != "https"
                or not parsed_image_url.netloc
                or not parsed_image_url.path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
            ):
                raise ValueError(f"Scene {scene.scene_number} is missing a valid public image URL")
            elements = [{
                "type": "image",
                "src": image_url,
                "resize": "cover",
                "duration": scene.duration,
            }]
            elements.extend([
                {
                    "type": "voice",
                    "text": scene.voiceover,
                    "voice": DEFAULT_VOICE_ID,
                    "model": VOICE_MODEL,
                },
                {
                    "type": "text",
                    "text": scene.on_screen_text,
                    "settings": {
                        "font-size": 48,
                        "color": "#FFFFFF",
                        "background-color": "#101820B8",
                        "padding": "18px 28px",
                        "border-radius": "8px",
                        "vertical-position": "bottom",
                        "horizontal-position": "center",
                    },
                },
            ])
            scene_payload = {
                "duration": scene.duration,
                "background-color": "#26364A",
                "elements": elements,
            }
            if scene.scene_number < len(validated.scenes):
                scene_payload["transition"] = {"type": "xfade", "style": "fade", "duration": 0.25}
            scenes.append(scene_payload)

        return {
            "resolution": "full-hd",
            "scenes": scenes,
        }

    def create_movie(
        self,
        script: Dict[str, Any],
        image_urls: list[str] | None = None,
        scene_assets: list[Dict[str, Any] | None] | None = None,
    ) -> Dict[str, Any]:
        payload = self.build_movie_payload(
            script,
            image_urls=image_urls,
            scene_assets=scene_assets,
        )
        try:
            response = self._client.post("/movies", json=payload)
        except httpx.HTTPError as exc:
            raise JSON2VideoError("JSON2Video submission failed") from exc
        if response.status_code in {401, 403}:
            raise JSON2VideoError("JSON2Video authentication failed", response.status_code)
        if response.status_code == 429:
            raise JSON2VideoError("JSON2Video quota is exhausted", response.status_code)
        if response.is_error:
            raise JSON2VideoError("JSON2Video rejected the movie payload", response.status_code)
        data = response.json()
        project_id = data.get("project") or data.get("project_id") or data.get("id")
        if not project_id:
            raise JSON2VideoError("JSON2Video returned no project ID")
        return {"project_id": str(project_id), "status": "submitted"}

    def get_movie_status(self, project_id: str) -> Dict[str, Any]:
        try:
            response = self._client.get("/movies", params={"project": project_id})
        except httpx.HTTPError as exc:
            raise JSON2VideoError("JSON2Video status request failed") from exc
        if response.status_code in {401, 403}:
            raise JSON2VideoError("JSON2Video authentication failed", response.status_code)
        if response.status_code == 429:
            raise JSON2VideoError("JSON2Video quota is exhausted", response.status_code)
        if response.is_error:
            raise JSON2VideoError("JSON2Video status request failed", response.status_code)
        data = response.json()
        if isinstance(data, list):
            movie = data[0] if data else {}
        elif isinstance(data, dict):
            # The single-project v2 response wraps status and playback metadata
            # in `movie`; some older/list responses return the movie directly.
            movie = data.get("movie") or data
        else:
            movie = {}
        if not isinstance(movie, dict):
            raise JSON2VideoError("JSON2Video returned an invalid movie status response")
        returned_project_id = movie.get("project") or movie.get("project_id")
        if returned_project_id and str(returned_project_id) != str(project_id):
            raise JSON2VideoError("JSON2Video returned status for a different project")
        status_value = str(movie.get("status") or "rendering").lower()
        result_url = movie.get("url") or movie.get("video_url") or movie.get("result_url")
        return {
            "project_id": str(returned_project_id or project_id),
            "status": status_value,
            "result_url": result_url,
            "message": movie.get("message"),
        }
