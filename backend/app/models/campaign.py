from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class Campaign(Base):
    """Marketing campaign owned by a single user. Future AI results attach here."""

    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    product_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    target_audience = Column(Text, nullable=False)
    platform = Column(String(50), nullable=False, index=True)
    objective = Column(String(50), nullable=False)
    tone = Column(String(50), nullable=False)
    budget = Column(Numeric(12, 2), nullable=True)
    keywords = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="Draft", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="campaigns")
    creatives = relationship("Creative", back_populates="campaign", cascade="all, delete-orphan")
    audience_analysis_runs = relationship(
        "AudienceAnalysisRun", back_populates="campaign", cascade="all, delete-orphan"
    )
    performance_records = relationship(
        "CampaignPerformanceDaily", back_populates="campaign", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name} user_id={self.user_id}>"
