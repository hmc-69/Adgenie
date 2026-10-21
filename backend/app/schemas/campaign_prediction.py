from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.campaign import CampaignObjective, CampaignPlatform, CampaignTone


class CampaignPredictionFeatures(BaseModel):
    """Validated pre-launch features already stored on the campaign record."""

    product_name: str = Field(..., min_length=1, max_length=150)
    description: str = Field(..., min_length=1, max_length=4000)
    target_audience: str = Field(..., min_length=1, max_length=2000)
    platform: CampaignPlatform
    objective: CampaignObjective
    tone: CampaignTone
    budget: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    keywords: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("product_name", "description", "target_audience")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prediction campaign text fields cannot be blank.")
        return value

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value is not None else None


class CampaignPredictionValues(BaseModel):
    ctr_percent: float = Field(..., ge=0, le=100)
    conversion_rate_percent: float = Field(..., ge=0, le=100)


class TargetEvaluation(BaseModel):
    selected_model: str
    test_mae: Optional[float] = None
    test_rmse: Optional[float] = None
    test_r2: Optional[float] = None
    baseline_model: str
    baseline_test_mae: Optional[float] = None
    baseline_test_rmse: Optional[float] = None
    baseline_test_r2: Optional[float] = None
    meaningful_improvement_over_baseline: bool


class CampaignPredictionEvaluation(BaseModel):
    dataset_type: str
    ctr: TargetEvaluation
    conversion_rate: TargetEvaluation


class CampaignPerformancePredictionResponse(BaseModel):
    campaign_id: int
    prediction_type: str
    model_version: str
    predictions: CampaignPredictionValues
    units: dict[str, str]
    evaluation: CampaignPredictionEvaluation
    output_bound_strategy: str
    limitations: list[str]

    model_config = ConfigDict(from_attributes=True)
