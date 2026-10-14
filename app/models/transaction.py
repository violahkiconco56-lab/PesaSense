from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "import_fingerprint",
            name="uq_transactions_account_import_fingerprint",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(24, 8))
    transaction_type = Column(String)
    category = Column(String)
    description = Column(String)
    # How often income is received: "one_time", "daily", "weekly", "monthly".
    # Only meaningful for income records; left null for expenses.
    frequency = Column(String, nullable=True)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = Column(Integer, ForeignKey("users.id"))
    account_id = Column(
        Integer, ForeignKey("financial_accounts.id", ondelete="SET NULL"), nullable=True
    )
    import_fingerprint = Column(String(64), nullable=True)

    user = relationship("User", back_populates="transactions")