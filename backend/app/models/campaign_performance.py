from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CampaignPerformanceDaily(Base):
    __tablename__ = "campaign_performance_daily"
    __table_args__ = (
        UniqueConstraint("campaign_id", "date", name="uq_campaign_performance_campaign_date"),
        CheckConstraint("impressions >= 0", name="ck_performance_impressions_nonnegative"),
        CheckConstraint("clicks >= 0", name="ck_performance_clicks_nonnegative"),
        CheckConstraint("conversions >= 0", name="ck_performance_conversions_nonnegative"),
        CheckConstraint("spend >= 0", name="ck_performance_spend_nonnegative"),
        CheckConstraint("revenue IS NULL OR revenue >= 0", name="ck_performance_revenue_nonnegative"),
        CheckConstraint("clicks <= impressions", name="ck_performance_clicks_within_impressions"),
        CheckConstraint("conversions <= clicks", name="ck_performance_conversions_within_clicks"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    campaign_id = Column(
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False)
    impressions = Column(Integer, nullable=False)
    clicks = Column(Integer, nullable=False)
    conversions = Column(Integer, nullable=False)
    spend = Column(Numeric(12, 2), nullable=False)
    revenue = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    campaign = relationship("Campaign", back_populates="performance_records")
