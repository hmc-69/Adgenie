from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audience_analysis import AudienceAnalysisRun
from app.models.campaign import Campaign
from app.schemas.audience_analysis import AudienceAnalysisProviderResult, AudienceAnalysisResult
from app.services.audience_classifier import AudienceClassifierError, predict_audience_archetype
from app.services.campaign_service import get_owned_campaign
from app.services.creative.text_generator import get_provider


logger = logging.getLogger(__name__)


def build_audience_analysis_snapshot(campaign: Campaign) -> Dict[str, Any]:
    fields = (
        "product_name",
        "description",
        "target_audience",
        "platform",
        "objective",
        "tone",
        "keywords",
        "budget",
    )
    snapshot: Dict[str, Any] = {}
    for field in fields:
        value = getattr(campaign, field, None)
        if isinstance(value, Decimal):
            value = str(value)
        if isinstance(value, str):
            value = value.strip() or None
        snapshot[field] = value
    return snapshot


def create_audience_analysis(
    db: Session,
    campaign_id: int,
    user_id: int,
) -> AudienceAnalysisRun:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    snapshot = build_audience_analysis_snapshot(campaign)

    prediction = None
    if settings.AUDIENCE_CLASSIFIER_ENABLED:
        try:
            # Resolve the prediction first so an unavailable artifact fails clearly
            # without allowing the text provider to stand in for the classifier.
            prediction = predict_audience_archetype(snapshot)
        except AudienceClassifierError as exc:
            logger.error("Configured audience classifier is unavailable for campaign %s: %s", campaign_id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The audience classifier is enabled but its local model is unavailable or incompatible.",
            ) from None

    try:
        provider = get_provider()
    except ValueError:
        logger.warning("Audience analysis provider is not configured for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audience analysis is unavailable because the configured AI provider is not ready.",
        ) from None

    try:
        raw_result = provider.generate_audience_analysis(snapshot)
        provider_result = AudienceAnalysisProviderResult.model_validate(raw_result)
        result_data = provider_result.model_dump()
        if prediction is not None:
            result_data["model_prediction"] = prediction
        result = AudienceAnalysisResult.model_validate(result_data)
    except ValidationError as exc:
        validation_details = [
            {
                "location": ".".join(str(part) for part in error.get("loc", ())),
                "message": str(error.get("msg", "Validation failed"))[:240],
                "type": error.get("type", "unknown"),
            }
            for error in exc.errors(include_url=False)[:20]
        ]
        logger.warning(
            "Audience analysis response failed schema validation for campaign %s: %s",
            campaign_id,
            validation_details,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider returned an invalid audience analysis. Please try again.",
        ) from None
    except ValueError:
        logger.warning("Audience analysis provider could not return valid structured output for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider returned an invalid audience analysis. Please try again.",
        ) from None
    except Exception as exc:
        # Keep provider payloads and exception text out of logs; SDK errors can
        # include request details. The exception type and HTTP status are
        # enough to distinguish configuration, quota, and transient failures.
        provider_status = getattr(exc, "code", None)
        logger.error(
            "Audience analysis provider failed for campaign %s (error_type=%s, provider_status=%s)",
            campaign_id,
            type(exc).__name__,
            provider_status if isinstance(provider_status, (int, str)) else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audience analysis is temporarily unavailable. Please try again.",
        ) from None

    provider_model = getattr(provider, "model", None)
    if not isinstance(provider_model, str):
        provider_model = None

    run = AudienceAnalysisRun(
        campaign_id=campaign.id,
        analysis_type="audience_analysis",
        input_snapshot=snapshot,
        result=result.model_dump(),
        provider=settings.AI_PROVIDER,
        model=provider_model,
    )
    try:
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    except SQLAlchemyError:
        db.rollback()
        logger.error("Audience analysis persistence failed for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The audience analysis could not be saved. Please try again.",
        ) from None


def get_audience_analysis_history(
    db: Session,
    campaign_id: int,
    user_id: int,
) -> list[AudienceAnalysisRun]:
    campaign = get_owned_campaign(db, campaign_id=campaign_id, user_id=user_id)
    try:
        return (
            db.query(AudienceAnalysisRun)
            .filter(AudienceAnalysisRun.campaign_id == campaign.id)
            .order_by(AudienceAnalysisRun.created_at.desc(), AudienceAnalysisRun.id.desc())
            .all()
        )
    except SQLAlchemyError:
        logger.error("Audience analysis history lookup failed for campaign %s", campaign_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audience analysis history could not be loaded. Please try again.",
        ) from None
