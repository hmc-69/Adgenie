from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CampaignPlatform(str, Enum):
    INSTAGRAM = "Instagram"
    FACEBOOK = "Facebook"
    GOOGLE_ADS = "Google Ads"
    LINKEDIN = "LinkedIn"


class CampaignObjective(str, Enum):
    BRAND_AWARENESS = "Brand Awareness"
    PRODUCT_PROMOTION = "Product Promotion"
    LEAD_GENERATION = "Lead Generation"
    WEBSITE_TRAFFIC = "Website Traffic"
    SALES = "Sales"


class CampaignTone(str, Enum):
    PROFESSIONAL = "Professional"
    CASUAL = "Casual"
    FRIENDLY = "Friendly"
    EXCITING = "Exciting"
    PERSUASIVE = "Persuasive"


class CampaignStatus(str, Enum):
    DRAFT = "Draft"
    ACTIVE = "Active"
    COMPLETED = "Completed"


def _require_non_empty(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be empty or whitespace only")
    return stripped


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Campaign name")
    product_name: str = Field(..., min_length=1, max_length=150, description="Product or service name")
    description: str = Field(..., min_length=1, max_length=4000, description="Campaign description")
    target_audience: str = Field(..., min_length=1, max_length=2000, description="Intended audience")
    platform: CampaignPlatform
    objective: CampaignObjective
    tone: CampaignTone
    budget: Optional[Decimal] = Field(default=None, ge=0, description="Optional non-negative budget")
    keywords: Optional[str] = Field(default=None, max_length=2000)
    status: CampaignStatus = Field(default=CampaignStatus.DRAFT)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _require_non_empty(value, "Campaign name")

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, value: str) -> str:
        return _require_non_empty(value, "Product name")

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _require_non_empty(value, "Description")

    @field_validator("target_audience")
    @classmethod
    def validate_target_audience(cls, value: str) -> str:
        return _require_non_empty(value, "Target audience")

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    target_audience: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    platform: Optional[CampaignPlatform] = None
    objective: Optional[CampaignObjective] = None
    tone: Optional[CampaignTone] = None
    budget: Optional[Decimal] = Field(default=None, ge=0)
    keywords: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[CampaignStatus] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _require_non_empty(value, "Campaign name")

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _require_non_empty(value, "Product name")

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _require_non_empty(value, "Description")

    @field_validator("target_audience")
    @classmethod
    def validate_target_audience(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _require_non_empty(value, "Target audience")

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CampaignResponse(BaseModel):
    id: int
    name: str
    product_name: str
    description: str
    target_audience: str
    platform: str
    objective: str
    tone: str
    budget: Optional[Decimal] = None
    keywords: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignListResponse(BaseModel):
    campaigns: List[CampaignResponse]
    total: int
