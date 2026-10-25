import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.audience_analysis import (
    AudienceArchetypePrediction,
    AudienceAnalysisHistoryResponse,
    AudienceAnalysisRunResponse,
)
from app.services.audience_analysis_service import (
    create_audience_analysis,
    get_audience_analysis_history,
)
from app.services.audience_classifier import AudienceClassifierError, predict_audience_archetype
from app.core.config import settings


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns/{campaign_id}/audience-analysis", tags=["Audience Analysis"])


@router.post(
    "",
    response_model=AudienceAnalysisRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and save AI audience recommendations for an owned campaign",
)
def create_audience_analysis_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info("Audience analysis POST received for campaign_id=%s", campaign_id)
    return create_audience_analysis(db=db, campaign_id=campaign_id, user_id=current_user.id)


@router.get(
    "",
    response_model=AudienceAnalysisHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get saved audience-analysis runs for an owned campaign",
)
def get_audience_analysis_history_endpoint(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analyses = get_audience_analysis_history(db=db, campaign_id=campaign_id, user_id=current_user.id)
    response_analyses = [AudienceAnalysisRunResponse.model_validate(run) for run in analyses]
    if settings.AUDIENCE_CLASSIFIER_ENABLED:
        for response in response_analyses:
            if response.result.model_prediction is not None:
                continue
            try:
                prediction = predict_audience_archetype(response.input_snapshot)
                response.result.model_prediction = AudienceArchetypePrediction.model_validate(prediction)
            except AudienceClassifierError:
                logger.exception("Audience classifier unavailable for saved run %s", response.id)
    return AudienceAnalysisHistoryResponse(analyses=response_analyses, total=len(response_analyses))
