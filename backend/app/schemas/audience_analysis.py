from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AudienceSegment(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    relevant_interests: List[str] = Field(..., min_length=1)
    needs_pain_points: List[str] = Field(..., min_length=1)
    motivations: List[str] = Field(..., min_length=1)
    recommended_message_angle: str = Field(..., min_length=1)


class PlatformTargetingApproach(BaseModel):
    platform: str = Field(..., min_length=1)
    approaches: List[str] = Field(..., min_length=1)


class AudienceArchetypePrediction(BaseModel):
    predicted_archetype: str = Field(..., min_length=1)
    model_identifier: str = Field(..., min_length=1)
    model_status: str = Field(..., min_length=1)
    class_scores: Dict[str, float]
    score_type: str = Field(..., min_length=1)


class AudienceAnalysisProviderResult(BaseModel):
    """Structured audience recommendations returned by Gemini or the mock provider."""

    recommendation_label: str = (
        "AI-generated recommendations based on campaign context; not verified audience data."
    )
    audience_overview: str = Field(..., min_length=1)
    segments: List[AudienceSegment] = Field(..., min_length=2)
    targeting_approaches: List[PlatformTargetingApproach] = Field(..., min_length=1)
    messaging_recommendations: List[str] = Field(..., min_length=1)
    creative_considerations: List[str] = Field(..., min_length=1)
    assumptions: List[str]
    limitations: List[str] = Field(..., min_length=1)
    missing_information: List[str]


class AudienceAnalysisResult(AudienceAnalysisProviderResult):
    """Persisted API result, including optional backend-only model metadata."""

    # Optional additive field: older saved runs and existing clients remain valid.
    model_prediction: Optional[AudienceArchetypePrediction] = None


class AudienceAnalysisRunResponse(BaseModel):
    id: int
    campaign_id: int
    analysis_type: str
    input_snapshot: dict
    result: AudienceAnalysisResult
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AudienceAnalysisHistoryResponse(BaseModel):
    analyses: List[AudienceAnalysisRunResponse]
    total: int
