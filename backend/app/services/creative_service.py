from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.creative import Creative
from app.schemas.creative import CreativeGenerateRequest, CreativeSaveRequest, CreativeType
from app.services.creative.providers.cloudflare_image_provider import CloudflareImageProviderError
from app.services.creative.text_generator import (
    build_image_generation_prompt,
    generate_image_brief,
    generate_video_script,
    get_image_provider,
)
from app.services.storage.supabase_storage import (
    SupabaseStorageError,
    SupabaseStorageNotFoundError,
    get_supabase_storage_service,
)

logger = logging.getLogger(__name__)


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
        logger.exception("Image creative generation failed for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation is temporarily unavailable. Please try again.",
        ) from exc


def generate_video_creative(db: Session, campaign_id: int, user_id: int) -> Dict[str, Any]:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    try:
        return build_video_script_payload(campaign)
    except Exception as exc:  # pragma: no cover - provider integration layer
        logger.exception("Video creative generation failed for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation is temporarily unavailable. Please try again.",
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


def generate_ad_image_for_creative(
    db: Session,
    campaign_id: int,
    creative_id: int,
    user_id: int,
    aspect_ratio: str,
    style: str,
) -> Dict[str, Any]:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    creative = get_creative_for_campaign(db, creative_id=creative_id, campaign_id=campaign_id, user_id=user_id)
    if creative.type != CreativeType.IMAGE.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected creative must be an image creative")

    creative_payload = creative.generated_content or {}
    if not creative_payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image creative content is missing")

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
    prompt = build_image_generation_prompt(
        campaign_payload,
        creative_payload,
        aspect_ratio,
        style,
    )

    try:
        provider = get_image_provider()
    except ValueError as exc:
        logger.error("Image provider configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image generation service is not configured.",
        ) from exc

    try:
        generated_image = provider.generate_image(prompt, aspect_ratio=aspect_ratio)
    except (CloudflareImageProviderError, ValueError) as exc:
        logger.exception("Cloudflare image generation failed for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to generate the advertisement image. Please try again.",
        ) from exc

    previous_image_path = creative.image_path
    storage_service = get_supabase_storage_service()
    try:
        storage_path = storage_service.upload_image(
            image_bytes=generated_image.content,
            content_type=generated_image.content_type,
            campaign_id=campaign.id,
            creative_id=creative.id,
        )
    except (SupabaseStorageError, ValueError) as exc:
        logger.exception("Generated image storage failed for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store the generated image. Please try again.",
        ) from exc

    relative_url = f"/api/creative/campaign/{campaign.id}/image/{creative.id}"

    creative.image_url = relative_url
    creative.image_path = storage_path
    creative.image_content_type = generated_image.content_type
    creative.image_aspect_ratio = aspect_ratio
    creative.image_style = style
    creative.image_resolution = None
    creative.generated_at = datetime.now(timezone.utc)
    creative.generated_content = {
        **creative.generated_content,
        "image_metadata": {
            "aspect_ratio": aspect_ratio,
            "style": style,
            "image_url": relative_url,
        },
    }

    try:
        db.add(creative)
        db.commit()
        db.refresh(creative)
    except SQLAlchemyError:
        db.rollback()
        try:
            storage_service.delete_image(storage_path)
        except SupabaseStorageError:
            logger.warning("Failed to clean up uploaded image after database failure")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist generated image")

    if previous_image_path and previous_image_path != storage_path:
        try:
            storage_service.delete_image(previous_image_path)
        except SupabaseStorageError:
            logger.warning("Failed to delete previous Firebase image for creative %s", creative.id)

    return {
        "campaign_id": campaign.id,
        "creative_id": creative.id,
        "image_url": relative_url,
        "aspect_ratio": aspect_ratio,
        "style": style,
        "prompt": prompt,
        "generated_content": creative.generated_content,
        "generated_at": creative.generated_at,
    }


def get_generated_image(
    db: Session,
    campaign_id: int,
    creative_id: int,
    user_id: int,
) -> tuple[bytes, str]:
    creative = get_creative_for_campaign(
        db,
        creative_id=creative_id,
        campaign_id=campaign_id,
        user_id=user_id,
    )
    if not creative.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated image not found")
    try:
        image_bytes = get_supabase_storage_service().download_image(creative.image_path)
    except SupabaseStorageNotFoundError as exc:
        logger.warning("Supabase image is unavailable for creative %s", creative_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated image not found") from exc
    except SupabaseStorageError as exc:
        logger.exception("Supabase image retrieval failed for creative %s", creative_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image storage is temporarily unavailable. Please try again.",
        ) from exc
    return image_bytes, creative.image_content_type or "application/octet-stream"
