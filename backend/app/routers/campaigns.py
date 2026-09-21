from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.auth import MessageResponse
from app.schemas.campaign import (
    CampaignCreate,
    CampaignListResponse,
    CampaignResponse,
    CampaignUpdate,
)
from app.services.campaign_service import (
    create_campaign,
    delete_campaign,
    get_campaign_for_user,
    list_user_campaigns,
    update_campaign,
)

router = APIRouter(prefix="/api/campaigns", tags=["Campaigns"])


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a campaign for the authenticated user",
)
def create_campaign_endpoint(
    campaign_in: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_campaign(db=db, user_id=current_user.id, campaign_in=campaign_in)


@router.get(
    "",
    response_model=CampaignListResponse,
    status_code=status.HTTP_200_OK,
    summary="List campaigns belonging to the authenticated user",
)
def list_campaigns_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    campaigns = list_user_campaigns(db=db, user_id=current_user.id)
    return CampaignListResponse(campaigns=campaigns, total=len(campaigns))


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a campaign owned by the authenticated user",
)
def get_campaign_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_campaign_for_user(db=db, campaign_id=campaign_id, user_id=current_user.id)


@router.put(
    "/{campaign_id}",
    response_model=CampaignResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a campaign owned by the authenticated user",
)
def update_campaign_endpoint(
    campaign_id: int,
    campaign_in: CampaignUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_campaign(
        db=db,
        campaign_id=campaign_id,
        user_id=current_user.id,
        campaign_in=campaign_in,
    )


@router.delete(
    "/{campaign_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a campaign owned by the authenticated user",
)
def delete_campaign_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delete_campaign(db=db, campaign_id=campaign_id, user_id=current_user.id)
    return MessageResponse(message="Campaign deleted successfully.")
