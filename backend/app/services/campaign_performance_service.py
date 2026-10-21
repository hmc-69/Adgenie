from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.campaign_performance import CampaignPerformanceDaily
from app.services.campaign_service import get_owned_campaign


CENT = Decimal("0.01")


def _filtered_records(db: Session, campaign_id: int, start_date: date | None, end_date: date | None):
    query = db.query(CampaignPerformanceDaily).filter(
        CampaignPerformanceDaily.campaign_id == campaign_id
    )
    if start_date is not None:
        query = query.filter(CampaignPerformanceDaily.date >= start_date)
    if end_date is not None:
        query = query.filter(CampaignPerformanceDaily.date <= end_date)
    return query.order_by(CampaignPerformanceDaily.date.asc())


def _validate_range(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")


def create_performance_record(db: Session, campaign_id: int, user_id: int, data) -> CampaignPerformanceDaily:
    get_owned_campaign(db, campaign_id, user_id)
    record = CampaignPerformanceDaily(campaign_id=campaign_id, **data.model_dump())
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except IntegrityError as exc:
        db.rollback()
        existing_record = db.query(CampaignPerformanceDaily).filter(
            CampaignPerformanceDaily.campaign_id == campaign_id,
            CampaignPerformanceDaily.date == data.date,
        ).first()
        if existing_record is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A performance record already exists for this campaign and date.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database constraint prevented this performance record from being saved.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while recording campaign performance.",
        ) from exc


def list_performance_records(
    db: Session,
    campaign_id: int,
    user_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[CampaignPerformanceDaily]:
    get_owned_campaign(db, campaign_id, user_id)
    _validate_range(start_date, end_date)
    try:
        return _filtered_records(db, campaign_id, start_date, end_date).all()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="A database error occurred while loading campaign performance.") from exc


def get_performance_analytics(
    db: Session,
    campaign_id: int,
    user_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    get_owned_campaign(db, campaign_id, user_id)
    _validate_range(start_date, end_date)
    records = _filtered_records(db, campaign_id, start_date, end_date).all()
    impressions = sum(record.impressions for record in records)
    clicks = sum(record.clicks for record in records)
    conversions = sum(record.conversions for record in records)
    spend = sum((record.spend for record in records), Decimal("0.00"))
    revenue_records = [record for record in records if record.revenue is not None]
    revenue = (
        sum((record.revenue for record in revenue_records), Decimal("0.00"))
        if records and len(revenue_records) == len(records)
        else None
    )

    def rounded(value: Decimal | None) -> Decimal | None:
        return value.quantize(CENT, rounding=ROUND_HALF_UP) if value is not None else None

    return {
        "campaign_id": campaign_id,
        "start_date": start_date,
        "end_date": end_date,
        "record_count": len(records),
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "spend": spend,
        "revenue": revenue,
        "ctr_percent": rounded(Decimal(clicks) * 100 / impressions) if impressions else None,
        "conversion_rate_percent": rounded(Decimal(conversions) * 100 / clicks) if clicks else None,
        "cpc": rounded(spend / clicks) if clicks else None,
        "roi_percent": (
            rounded((revenue - spend) * 100 / spend)
            if revenue is not None and spend
            else None
        ),
        "source": "manually_entered",
    }
