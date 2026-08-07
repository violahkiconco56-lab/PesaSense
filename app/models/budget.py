from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)

    category = Column(String)
    limit_amount = Column(Float)
    month = Column(Integer)   # 1-12
    year = Column(Integer)    # e.g. 2026

    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="budgets")