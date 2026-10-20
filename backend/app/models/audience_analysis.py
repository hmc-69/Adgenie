from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class AudienceAnalysisRun(Base):
    __tablename__ = "audience_analysis_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    campaign_id = Column(
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_type = Column(String(40), nullable=False, default="audience_analysis")
    input_snapshot = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    provider = Column(String(40), nullable=True)
    model = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    campaign = relationship("Campaign", back_populates="audience_analysis_runs")
