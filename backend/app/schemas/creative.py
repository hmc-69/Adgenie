from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ImageCreativeBrief(BaseModel):
    headline: str
    primary_text: str
    description: str
    call_to_action: str
    hashtags: List[str]
    visual_direction: str


class VideoScene(BaseModel):
    scene_number: int
    duration: str
    visual: str
    voiceover: str
    on_screen_text: str


class VideoCreativeScript(BaseModel):
    title: str
    duration: str
    scenes: List[VideoScene]
    final_cta: str


class CreativeGenerationResponse(BaseModel):
    campaign_id: int
    type: CreativeType
    generated_content: Dict[str, Any]


class CreativeRecordResponse(BaseModel):
    id: int
    campaign_id: int
    type: CreativeType
    generated_content: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreativeListResponse(BaseModel):
    creatives: List[CreativeRecordResponse]
    total: int
