from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.creative import (
    CreativeGenerationResponse,
    CreativeGenerateRequest,
    CreativeListResponse,
    CreativeRecordResponse,
    CreativeSaveRequest,
    CreativeType,
    ImageGenerationConfigResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from app.services.creative_service import (
    create_creative_record,
    generate_ad_image_for_creative,
    generate_image_creative,
    generate_video_creative,
    get_generated_image,
    get_creative_for_campaign,
    list_creatives_for_campaign,
)

router = APIRouter(prefix="/api/creative", tags=["Creative"])


@router.post(
    "/image-brief",
    response_model=CreativeGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate an image ad creative brief for the authenticated user and campaign",
)
def generate_image_brief_endpoint(
    payload: CreativeGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = generate_image_creative(db=db, campaign_id=payload.campaign_id, user_id=current_user.id)
    return CreativeGenerationResponse(
        campaign_id=payload.campaign_id,
        type=CreativeType.IMAGE,
        generated_content=content,
    )


@router.post(
    "/video-script",
    response_model=CreativeGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a video ad script for the authenticated user and campaign",
)
def generate_video_script_endpoint(
    payload: CreativeGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = generate_video_creative(db=db, campaign_id=payload.campaign_id, user_id=current_user.id)
    return CreativeGenerationResponse(
        campaign_id=payload.campaign_id,
        type=CreativeType.VIDEO,
        generated_content=content,
    )


@router.get(
    "/campaign/{campaign_id}",
    response_model=CreativeListResponse,
    status_code=status.HTTP_200_OK,
    summary="List saved creative assets for a campaign",
)
def list_creatives_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    creatives = list_creatives_for_campaign(db=db, campaign_id=campaign_id, user_id=current_user.id)
    return CreativeListResponse(
        creatives=[CreativeRecordResponse.model_validate(item) for item in creatives],
        total=len(creatives),
    )


@router.get(
    "/image-config",
    response_model=ImageGenerationConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supported image generation aspect ratios and styles",
)
def get_image_generation_config(
    current_user: User = Depends(get_current_user),
):
    return ImageGenerationConfigResponse(
        aspect_ratios=["1:1", "4:5", "9:16", "16:9", "3:4"],
        styles=["AI Recommended", "Photographic", "Minimal", "Editorial", "Bold Graphic", "Luxury", "Playful"],
    )


@router.post(
    "/image",
    response_model=ImageGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a marketing advertisement image for an existing image brief",
)
def generate_image_endpoint(
    payload: ImageGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = generate_ad_image_for_creative(
        db=db,
        campaign_id=payload.campaign_id,
        creative_id=payload.creative_id,
        user_id=current_user.id,
        aspect_ratio=payload.aspect_ratio,
        style=payload.style,
    )
    return ImageGenerationResponse(**result)


@router.get(
    "/campaign/{campaign_id}/image/{creative_id}",
    status_code=status.HTTP_200_OK,
    summary="Serve a generated image for an owned campaign creative",
)
def serve_generated_image(
    campaign_id: int,
    creative_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    image_bytes, content_type = get_generated_image(
        db=db,
        campaign_id=campaign_id,
        creative_id=creative_id,
        user_id=current_user.id,
    )
    return Response(content=image_bytes, media_type=content_type)


@router.post(
    "/save",
    response_model=CreativeRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist a generated creative for the authenticated user and campaign",
)
def save_creative_endpoint(
    payload: CreativeSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    creative = create_creative_record(db=db, creative_in=payload, user_id=current_user.id)
    return CreativeRecordResponse.model_validate(creative)
