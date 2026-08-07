from pydantic import BaseModel
from datetime import datetime


class TransactionCreate(BaseModel):
    amount: float
    transaction_type: str
    category: str
    description: str | None = None


class TransactionResponse(BaseModel):
    id: int
    amount: float
    transaction_type: str
    category: str
    description: str | None
    date: datetime
    user_id: int

    class Config:
        from_attributes = True

class TransactionUpdate(BaseModel):
    amount: float | None = None
    transaction_type: str | None = None
    category: str | None = None
    description: str | None = None