from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.creative import Creative
from app.schemas.creative import CreativeGenerateRequest, CreativeSaveRequest, CreativeType, VideoCreativeScript
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
from app.services.creative.providers.json2video_provider import JSON2VideoError, JSON2VideoProvider
from app.services.creative.providers.pexels_image_search import PexelsImageSearch

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
    except ValueError as exc:
        logger.warning("Generated video script was rejected for campaign %s: %s", campaign_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Generated video script is invalid: {exc}",
        ) from exc
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


def _get_owned_video_creative(db: Session, campaign_id: int, creative_id: int, user_id: int) -> Creative:
    creative = get_creative_for_campaign(db, creative_id, campaign_id, user_id)
    if creative.type != CreativeType.VIDEO.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected creative must be a video creative")
    try:
        VideoCreativeScript.model_validate(creative.generated_content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Saved video script is invalid") from exc
    return creative


def start_video_render(db: Session, campaign_id: int, creative_id: int, user_id: int) -> dict[str, Any]:
    creative = _get_owned_video_creative(db, campaign_id, creative_id, user_id)
    if creative.video_project_id:
        return {
            "campaign_id": campaign_id, "creative_id": creative_id,
            "project_id": creative.video_project_id, "status": creative.video_status or "submitted",
            "duration": creative.video_duration or 0, "video_url": None,
        }
    try:
        script = VideoCreativeScript.model_validate(creative.generated_content)
        campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
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
        search = PexelsImageSearch()
        scene_assets = []
        missing_scene_numbers = []
        logger.info("Preparing image assets for %s scenes in campaign %s creative %s", len(script.scenes), campaign_id, creative_id)
        for scene in script.scenes:
            query = scene.visual_description or scene.visual
            asset = search.search(query, campaign_payload)
            if not _has_public_image_url(asset):
                simple_query = _simplify_scene_image_query(query, campaign_payload.get("product_name", ""))
                if simple_query and simple_query.casefold() != query.casefold():
                    logger.info("Retrying image search with a simpler query for scene %s", scene.scene_number)
                    asset = search.search(simple_query, campaign_payload)
            is_valid_image_url = _has_public_image_url(asset)
            logger.info(
                "Video scene %s image URL valid=%s",
                scene.scene_number,
                is_valid_image_url,
            )
            if not is_valid_image_url:
                missing_scene_numbers.append(scene.scene_number)
                continue
            scene_assets.append({"visual_description": query, **asset, "fallback": None})
        if missing_scene_numbers:
            logger.error(
                "Image retrieval failed for campaign %s creative %s scenes %s; refusing to submit a blank render",
                campaign_id,
                creative_id,
                missing_scene_numbers,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not find publicly accessible images for video scene(s): "
                + ", ".join(str(number) for number in missing_scene_numbers)
                + ". Please retry after image search is available.",
            )
        result = JSON2VideoProvider().create_movie(script.model_dump(), scene_assets=scene_assets)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Video scene image validation failed: {exc}") from exc
    except JSON2VideoError as exc:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.status_code in {401, 403, 429} else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    creative.video_project_id = result["project_id"]
    creative.video_status = result["status"]
    creative.video_duration = script.duration
    creative.generated_content = {
        **creative.generated_content,
        "scene_assets": scene_assets,
        "video_render": {"project_id": result["project_id"], "status": result["status"]},
    }
    db.add(creative)
    db.commit()
    db.refresh(creative)
    return {
        "campaign_id": campaign_id, "creative_id": creative_id,
        "project_id": creative.video_project_id, "status": creative.video_status,
        "duration": creative.video_duration, "video_url": None,
    }


def _simplify_scene_image_query(visual_description: str, product_name: str) -> str:
    stop_words = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with", "showing", "photo", "landscape"}
    words = [
        word.strip(".,;:!?()[]{}\"'")
        for word in visual_description.split()
    ]
    keywords = [word for word in words if word and word.casefold() not in stop_words][:5]
    simple_query = " ".join(part for part in (" ".join(keywords), str(product_name or "").strip()) if part)
    return " ".join(simple_query.split())[:120]


def _has_public_image_url(asset: Any) -> bool:
    image_url = asset.get("image_url") if isinstance(asset, dict) else None
    try:
        parsed_url = urlparse(image_url) if isinstance(image_url, str) else None
    except ValueError:
        return False
    return bool(
        parsed_url
        and parsed_url.scheme == "https"
        and parsed_url.netloc
        and parsed_url.path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
    )


def update_video_render_status(db: Session, campaign_id: int, creative_id: int, user_id: int) -> dict[str, Any]:
    creative = _get_owned_video_creative(db, campaign_id, creative_id, user_id)
    if not creative.video_project_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Video rendering has not been started")
    if creative.video_path:
        return {
            "campaign_id": campaign_id,
            "creative_id": creative_id,
            "project_id": creative.video_project_id,
            "status": "completed",
            "duration": creative.video_duration or 0,
            "video_url": f"/api/creative/campaign/{campaign_id}/video/{creative_id}",
        }
    if creative.video_status == "failed":
        render = creative.generated_content.get("video_render", {})
        return {
            "campaign_id": campaign_id,
            "creative_id": creative_id,
            "project_id": creative.video_project_id,
            "status": "failed",
            "duration": creative.video_duration or 0,
            "video_url": None,
            "error": render.get("error"),
        }
    else:
        try:
            result = JSON2VideoProvider().get_movie_status(creative.video_project_id)
        except JSON2VideoError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        provider_status = result["status"]
        creative.video_status = provider_status
        if provider_status in {"error", "timeout"}:
            error = result.get("message") or f"JSON2Video render {provider_status}."
            creative.video_status = "failed"
            creative.generated_content = {
                **creative.generated_content,
                "video_render": {
                    "project_id": creative.video_project_id,
                    "status": "failed",
                    "error": error,
                },
            }
            db.add(creative)
            db.commit()
            db.refresh(creative)
            return {
                "campaign_id": campaign_id,
                "creative_id": creative_id,
                "project_id": creative.video_project_id,
                "status": "failed",
                "duration": creative.video_duration or 0,
                "video_url": None,
                "error": error,
            }
        if provider_status == "done" and not result.get("result_url"):
            error = "JSON2Video reports the render is done but returned no video URL."
            creative.video_status = "failed"
            creative.generated_content = {
                **creative.generated_content,
                "video_render": {
                    "project_id": creative.video_project_id,
                    "status": "failed",
                    "error": error,
                },
            }
            db.add(creative)
            db.commit()
            db.refresh(creative)
            return {
                "campaign_id": campaign_id,
                "creative_id": creative_id,
                "project_id": creative.video_project_id,
                "status": "failed",
                "duration": creative.video_duration or 0,
                "video_url": None,
                "error": error,
            }
        if result.get("result_url") and provider_status == "done":
            creative.video_result_url = result["result_url"]
            try:
                response = httpx.get(result["result_url"], timeout=httpx.Timeout(60.0, connect=10.0))
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if content_type != "video/mp4" or not response.content:
                    raise ValueError("JSON2Video returned an invalid MP4 response")
                creative.video_path = get_supabase_storage_service().upload_video(
                    response.content, campaign_id, creative_id
                )
            except (httpx.HTTPError, ValueError, SupabaseStorageError) as exc:
                creative.video_status = "failed"
                creative.generated_content = {
                    **creative.generated_content,
                    "video_render": {
                        "project_id": creative.video_project_id,
                        "status": "failed",
                        "video_url": result["result_url"],
                        "error": "The render completed, but AdGenie could not save the MP4 to private storage.",
                    },
                }
                db.add(creative)
                db.commit()
                logger.exception("Unable to store completed JSON2Video render for creative %s", creative_id)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="The render completed, but AdGenie could not save the MP4 to private storage. Please retry.",
                ) from exc
            creative.video_content_type = "video/mp4"
            creative.video_status = "completed"
            creative.generated_content = {
                **creative.generated_content,
                "video_render": {
                    "project_id": creative.video_project_id,
                    "status": "completed",
                    "video_url": result["result_url"],
                },
            }
    db.add(creative)
    db.commit()
    db.refresh(creative)
    return {
        "campaign_id": campaign_id, "creative_id": creative_id,
        "project_id": creative.video_project_id, "status": creative.video_status,
        "duration": creative.video_duration or 0,
        "video_url": f"/api/creative/campaign/{campaign_id}/video/{creative_id}" if creative.video_path else None,
        "error": None,
    }


def get_generated_video(db: Session, campaign_id: int, creative_id: int, user_id: int) -> tuple[bytes, str]:
    creative = _get_owned_video_creative(db, campaign_id, creative_id, user_id)
    if not creative.video_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered video not found")
    try:
        return get_supabase_storage_service().download_video(creative.video_path), creative.video_content_type or "video/mp4"
    except SupabaseStorageNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered video not found") from exc
    except SupabaseStorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Video storage is temporarily unavailable") from exc
