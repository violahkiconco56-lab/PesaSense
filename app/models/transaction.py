from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    amount = Column(Float, nullable=False)

    transaction_type = Column(
        String,
        nullable=False
    )
    # income or expense

    category = Column(
        String,
        nullable=False
    )

    description = Column(String)

    date = Column(
        DateTime,
        server_default=func.now()
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )