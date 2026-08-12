from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


TransactionType = Literal["income", "expense"]


class TransactionCreate(BaseModel):
    amount: float = Field(gt=0)
    transaction_type: TransactionType
    category: str = Field(min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    date: datetime | None = None

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        if isinstance(value, str):
            return value.strip().title()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


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
    amount: float | None = Field(default=None, gt=0)
    transaction_type: TransactionType | None = None
    category: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    date: datetime | None = None

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        if isinstance(value, str):
            return value.strip().title()
        return value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value
