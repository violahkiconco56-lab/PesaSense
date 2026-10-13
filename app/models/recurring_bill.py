from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime

from app.database import Base


class RecurringBill(Base):
    __tablename__ = "recurring_bills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    # "weekly", "monthly" or "yearly"
    frequency = Column(String, nullable=False, default="monthly")
    next_due_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)