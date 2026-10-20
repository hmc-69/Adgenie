from typing import Optional

from pydantic import BaseModel


class VideoRenderRequest(BaseModel):
    campaign_id: int
    creative_id: int


class VideoRenderResponse(BaseModel):
    campaign_id: int
    creative_id: int
    project_id: Optional[str] = None
    status: str
    duration: float
    video_url: Optional[str] = None
    error: Optional[str] = None
