from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CampaignPerformanceCreate(BaseModel):
    date: date
    impressions: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)
    conversions: int = Field(..., ge=0)
    spend: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    revenue: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def validate_metric_relationships(self):
        if self.clicks > self.impressions:
            raise ValueError("Clicks cannot exceed impressions.")
        if self.conversions > self.clicks:
            raise ValueError("Conversions cannot exceed clicks.")
        return self


class CampaignPerformanceResponse(BaseModel):
    id: int
    campaign_id: int
    date: date
    impressions: int
    clicks: int
    conversions: int
    spend: Decimal
    revenue: Optional[Decimal]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignPerformanceListResponse(BaseModel):
    records: List[CampaignPerformanceResponse]
    total: int


class CampaignPerformanceAnalyticsResponse(BaseModel):
    campaign_id: int
    start_date: Optional[date]
    end_date: Optional[date]
    record_count: int
    impressions: int
    clicks: int
    conversions: int
    spend: Decimal
    revenue: Optional[Decimal]
    ctr_percent: Optional[Decimal]
    conversion_rate_percent: Optional[Decimal]
    cpc: Optional[Decimal]
    roi_percent: Optional[Decimal]
    source: str = "manually_entered"
