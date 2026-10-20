from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_VIDEO_DURATION_SECONDS = 15
MIN_VIDEO_SCENES = 2
MAX_VIDEO_SCENES = 4


class CreativeType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class CreativeGenerateRequest(BaseModel):
    campaign_id: int = Field(..., gt=0, description="Campaign ID to source creative generation inputs")


class CreativeSaveRequest(BaseModel):
    campaign_id: int = Field(..., gt=0, description="Campaign ID that owns the saved creative")
    type: CreativeType = Field(..., description="Creative type to save")
    content: Dict[str, Any] = Field(..., description="Generated creative content to save")

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not value:
            raise ValueError("Creative content cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_video_content(self) -> "CreativeSaveRequest":
        if self.type == CreativeType.VIDEO:
            VideoCreativeScript.model_validate(self.content)
        return self


class ImageCreativeBrief(BaseModel):
    headline: str
    primary_text: str
    description: str
    call_to_action: str
    hashtags: List[str]
    visual_direction: str


class VideoScene(BaseModel):
    scene_number: int = Field(..., ge=1)
    duration: float = Field(..., ge=0, description="Scene duration in seconds")
    visual: str = Field(..., min_length=1)
    visual_description: Optional[str] = Field(default=None, min_length=1)
    visual_prompt: Optional[str] = Field(default=None, min_length=1)
    voiceover: str = Field(..., min_length=1)
    on_screen_text: str = Field(..., min_length=1)

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Scene duration must be greater than zero")
        return value


class VideoCreativeScript(BaseModel):
    title: str = Field(..., min_length=1)
    duration: float = Field(..., ge=0, le=MAX_VIDEO_DURATION_SECONDS)
    scenes: List[VideoScene] = Field(..., min_length=MIN_VIDEO_SCENES, max_length=MAX_VIDEO_SCENES)
    final_cta: str = Field(..., min_length=1)

    @field_validator("duration")
    @classmethod
    def validate_duration_value(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Video duration must be greater than zero")
        return value

    @model_validator(mode="after")
    def validate_duration(self) -> "VideoCreativeScript":
        scene_duration = sum(scene.duration for scene in self.scenes)
        if scene_duration > MAX_VIDEO_DURATION_SECONDS:
            raise ValueError(
                f"Video scene durations total {scene_duration:g} seconds; "
                f"maximum is {MAX_VIDEO_DURATION_SECONDS} seconds"
            )
        if abs(self.duration - scene_duration) > 0.01:
            raise ValueError("Video duration must equal the sum of scene durations")
        if self.scenes[-1].on_screen_text.strip().lower() != self.final_cta.strip().lower():
            raise ValueError("The final scene must include the final call to action as on-screen text")
        return self


class CreativeGenerationResponse(BaseModel):
    campaign_id: int
    type: CreativeType
    generated_content: Dict[str, Any]


class ImageGenerationConfigResponse(BaseModel):
    aspect_ratios: List[str] = Field(default_factory=lambda: ["1:1", "4:5", "9:16", "16:9", "3:4"])
    styles: List[str] = Field(default_factory=lambda: [
        "AI Recommended",
        "Photographic",
        "Minimal",
        "Editorial",
        "Bold Graphic",
        "Luxury",
        "Playful",
    ])


class ImageGenerationRequest(BaseModel):
    campaign_id: int = Field(..., gt=0, description="Campaign ID that owns the image")
    creative_id: int = Field(..., gt=0, description="Saved image creative to use as the brief source")
    aspect_ratio: str = Field(..., description="Image aspect ratio, for example 4:5")
    style: str = Field(..., description="Image visual style")

    @field_validator("aspect_ratio")
    @classmethod
    def validate_aspect_ratio(cls, value: str) -> str:
        allowed = {"1:1", "4:5", "9:16", "16:9", "3:4"}
        if value not in allowed:
            raise ValueError("Unsupported aspect ratio")
        return value

    @field_validator("style")
    @classmethod
    def validate_style(cls, value: str) -> str:
        allowed = {
            "AI Recommended",
            "Photographic",
            "Minimal",
            "Editorial",
            "Bold Graphic",
            "Luxury",
            "Playful",
        }
        if value not in allowed:
            raise ValueError("Unsupported visual style")
        return value


class ImageGenerationResponse(BaseModel):
    campaign_id: int
    creative_id: int
    image_url: str
    aspect_ratio: str
    style: str
    prompt: str
    generated_content: Dict[str, Any]
    generated_at: datetime

    @field_validator("generated_content", mode="before")
    @classmethod
    def hide_internal_image_path(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return value
        content = dict(value)
        metadata = content.get("image_metadata")
        if isinstance(metadata, dict) and "image_path" in metadata:
            content["image_metadata"] = {
                key: item for key, item in metadata.items() if key != "image_path"
            }
        return content


class CreativeRecordResponse(BaseModel):
    id: int
    campaign_id: int
    type: CreativeType
    generated_content: Dict[str, Any]
    image_url: Optional[str] = None
    image_aspect_ratio: Optional[str] = None
    image_style: Optional[str] = None
    image_resolution: Optional[str] = None
    video_project_id: Optional[str] = None
    video_status: Optional[str] = None
    video_duration: Optional[float] = None
    video_url: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("generated_content", mode="before")
    @classmethod
    def hide_internal_image_path(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return value
        content = dict(value)
        metadata = content.get("image_metadata")
        if isinstance(metadata, dict) and "image_path" in metadata:
            content["image_metadata"] = {
                key: item for key, item in metadata.items() if key != "image_path"
            }
        return content

    model_config = ConfigDict(from_attributes=True)


class CreativeListResponse(BaseModel):
    creatives: List[CreativeRecordResponse]
    total: int
