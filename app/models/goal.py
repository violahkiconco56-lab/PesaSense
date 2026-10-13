from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime

from app.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    target_amount = Column(Float, nullable=False)
    saved_amount = Column(Float, nullable=False, default=0)
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)