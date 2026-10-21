from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.campaign_performance import (
    CampaignPerformanceAnalyticsResponse,
    CampaignPerformanceCreate,
    CampaignPerformanceListResponse,
    CampaignPerformanceResponse,
)
from app.schemas.campaign_prediction import CampaignPerformancePredictionResponse
from app.services.campaign_prediction_service import predict_campaign_performance
from app.services.campaign_performance_service import (
    create_performance_record,
    get_performance_analytics,
    list_performance_records,
)

router = APIRouter(prefix="/api/campaigns/{campaign_id}/performance", tags=["Campaign Performance"])


@router.post("/predict", response_model=CampaignPerformancePredictionResponse)
def predict_campaign_performance_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return predict_campaign_performance(db, campaign_id, current_user.id)


@router.post("", response_model=CampaignPerformanceResponse, status_code=status.HTTP_201_CREATED)
def record_campaign_performance(
    campaign_id: int,
    data: CampaignPerformanceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_performance_record(db, campaign_id, current_user.id, data)


@router.get("", response_model=CampaignPerformanceListResponse)
def get_campaign_performance_records(
    campaign_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = list_performance_records(db, campaign_id, current_user.id, start_date, end_date)
    return CampaignPerformanceListResponse(records=records, total=len(records))


@router.get("/analytics", response_model=CampaignPerformanceAnalyticsResponse)
def get_campaign_performance_summary(
    campaign_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_performance_analytics(db, campaign_id, current_user.id, start_date, end_date)
