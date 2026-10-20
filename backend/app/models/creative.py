from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class Creative(Base):
    __tablename__ = "creatives"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(20), nullable=False, index=True)
    generated_content = Column(JSON, nullable=False)
    image_url = Column(String(500), nullable=True)
    image_path = Column(String(500), nullable=True)
    image_content_type = Column(String(50), nullable=True)
    image_aspect_ratio = Column(String(20), nullable=True)
    image_style = Column(String(50), nullable=True)
    image_resolution = Column(String(20), nullable=True)
    video_project_id = Column(String(100), nullable=True, unique=True)
    video_status = Column(String(30), nullable=True)
    video_path = Column(String(500), nullable=True)
    video_content_type = Column(String(50), nullable=True)
    video_duration = Column(Float, nullable=True)
    video_result_url = Column(String(1000), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    campaign = relationship("Campaign", back_populates="creatives")

    def __repr__(self) -> str:
        return f"<Creative id={self.id} campaign_id={self.campaign_id} type={self.type}>"
