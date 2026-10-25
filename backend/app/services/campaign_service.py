from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.services.storage.supabase_storage import (
    SupabaseStorageNotFoundError,
    get_supabase_storage_service,
)


CAMPAIGN_NOT_FOUND_DETAIL = "Campaign not found"


def _raise_database_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="A database error occurred while processing the campaign. Please try again.",
    )


def get_owned_campaign(db: Session, campaign_id: int, user_id: int) -> Campaign:
    """Return a campaign only if it belongs to the authenticated user.

    Unknown IDs and campaigns owned by someone else both return 404 so
    ownership is not leaked.
    """
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == user_id)
        .first()
    )
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CAMPAIGN_NOT_FOUND_DETAIL,
        )
    return campaign


def list_user_campaigns(db: Session, user_id: int) -> list[Campaign]:
    try:
        return (
            db.query(Campaign)
            .filter(Campaign.user_id == user_id)
            .order_by(Campaign.created_at.desc())
            .all()
        )
    except SQLAlchemyError:
        _raise_database_error()
        return []


def create_campaign(db: Session, user_id: int, campaign_in: CampaignCreate) -> Campaign:
    """Create a campaign owned by the authenticated user. Client-supplied user_id is ignored."""
    try:
        campaign = Campaign(
            user_id=user_id,
            name=campaign_in.name,
            product_name=campaign_in.product_name,
            description=campaign_in.description,
            target_audience=campaign_in.target_audience,
            platform=campaign_in.platform.value,
            objective=campaign_in.objective.value,
            tone=campaign_in.tone.value,
            budget=campaign_in.budget,
            keywords=campaign_in.keywords,
            status=campaign_in.status.value,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign
    except SQLAlchemyError:
        db.rollback()
        _raise_database_error()
        raise


def update_campaign(
    db: Session,
    campaign_id: int,
    user_id: int,
    campaign_in: CampaignUpdate,
) -> Campaign:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    updates = campaign_in.model_dump(exclude_unset=True)

    if "platform" in updates and campaign_in.platform is not None:
        updates["platform"] = campaign_in.platform.value
    if "objective" in updates and campaign_in.objective is not None:
        updates["objective"] = campaign_in.objective.value
    if "tone" in updates and campaign_in.tone is not None:
        updates["tone"] = campaign_in.tone.value
    if "status" in updates and campaign_in.status is not None:
        updates["status"] = campaign_in.status.value

    try:
        for field, value in updates.items():
            setattr(campaign, field, value)
        campaign.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(campaign)
        return campaign
    except SQLAlchemyError:
        db.rollback()
        _raise_database_error()
        raise


def delete_campaign(db: Session, campaign_id: int, user_id: int) -> None:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    # Clean storage before committing relational deletion. If a provider call
    # fails, the campaign and its object paths remain so deletion can be retried.
    media_paths: set[str] = set()
    creatives = list(campaign.creatives)
    for creative in creatives:
        if creative.image_path:
            media_paths.add(creative.image_path)
        if creative.video_path:
            media_paths.add(creative.video_path)
        content = creative.generated_content if isinstance(creative.generated_content, dict) else {}
        for scene in content.get("scene_assets", []):
            if isinstance(scene, dict) and scene.get("storage_path"):
                media_paths.add(scene["storage_path"])
    storage = get_supabase_storage_service()
    try:
        for storage_path in sorted(media_paths):
            try:
                if storage_path.lower().endswith(".mp4"):
                    storage.delete_video(storage_path)
                else:
                    storage.delete_image(storage_path)
            except SupabaseStorageNotFoundError:
                # Already absent is an idempotent cleanup success.
                continue
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Campaign media cleanup failed. The campaign was retained; retry deletion later.",
        ) from exc
    try:
        db.delete(campaign)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        _raise_database_error()


def get_campaign_for_user(db: Session, campaign_id: int, user_id: int) -> Optional[Campaign]:
    return get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
