from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.creative import Creative
from app.schemas.creative import CreativeGenerateRequest, CreativeSaveRequest, CreativeType
from app.services.creative.text_generator import generate_image_brief, generate_video_script


CREATIVE_NOT_FOUND_DETAIL = "Creative not found"


def _raise_database_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="A database error occurred while processing the creative. Please try again.",
    )


def get_owned_campaign(db: Session, campaign_id: int, user_id: int) -> Campaign:
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.user_id == user_id)
        .first()
    )
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign


def build_image_brief_payload(campaign: Campaign) -> Dict[str, Any]:
    campaign_payload = {
        "name": campaign.name,
        "product_name": campaign.product_name,
        "description": campaign.description,
        "target_audience": campaign.target_audience,
        "platform": campaign.platform,
        "objective": campaign.objective,
        "tone": campaign.tone,
        "keywords": campaign.keywords,
    }
    return generate_image_brief(campaign_payload)


def build_video_script_payload(campaign: Campaign) -> Dict[str, Any]:
    campaign_payload = {
        "name": campaign.name,
        "product_name": campaign.product_name,
        "description": campaign.description,
        "target_audience": campaign.target_audience,
        "platform": campaign.platform,
        "objective": campaign.objective,
        "tone": campaign.tone,
        "keywords": campaign.keywords,
    }
    return generate_video_script(campaign_payload)


def generate_image_creative(db: Session, campaign_id: int, user_id: int) -> Dict[str, Any]:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    try:
        return build_image_brief_payload(campaign)
    except Exception as exc:  # pragma: no cover - provider integration layer
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI creative generation failed: {str(exc) or 'Unknown error'}",
        ) from exc


def generate_video_creative(db: Session, campaign_id: int, user_id: int) -> Dict[str, Any]:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    try:
        return build_video_script_payload(campaign)
    except Exception as exc:  # pragma: no cover - provider integration layer
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI creative generation failed: {str(exc) or 'Unknown error'}",
        ) from exc


def list_creatives_for_campaign(db: Session, campaign_id: int, user_id: int) -> List[Creative]:
    get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    try:
        return (
            db.query(Creative)
            .filter(Creative.campaign_id == campaign_id)
            .order_by(Creative.created_at.desc())
            .all()
        )
    except SQLAlchemyError:
        _raise_database_error()
        return []


def create_creative_record(db: Session, creative_in: CreativeSaveRequest, user_id: int) -> Creative:
    get_owned_campaign(db, campaign_id=creative_in.campaign_id, user_id=user_id)
    try:
        creative = Creative(
            campaign_id=creative_in.campaign_id,
            type=creative_in.type.value,
            generated_content=creative_in.content,
        )
        db.add(creative)
        db.commit()
        db.refresh(creative)
        return creative
    except SQLAlchemyError:
        db.rollback()
        _raise_database_error()
        raise


def get_creative_for_campaign(db: Session, creative_id: int, campaign_id: int, user_id: int) -> Creative:
    get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    creative = (
        db.query(Creative)
        .filter(Creative.id == creative_id, Creative.campaign_id == campaign_id)
        .first()
    )
    if creative is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CREATIVE_NOT_FOUND_DETAIL)
    return creative
