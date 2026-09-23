from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TransactionType = Literal["income", "expense"]
IncomeFrequency = Literal["one_time", "daily", "weekly", "monthly"]


def normalize_frequency(value):
    """Accept friendly spellings and map them onto the stored values."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": None,
        "one_time": "one_time",
        "onetime": "one_time",
        "one_off": "one_time",
        "single": "one_time",
        "once": "one_time",
        "daily": "daily",
        "day": "daily",
        "everyday": "daily",
        "weekly": "weekly",
        "week": "weekly",
        "monthly": "monthly",
        "month": "monthly",
    }
    return aliases.get(cleaned, cleaned)


class TransactionCreate(BaseModel):
    amount: float = Field(gt=0)
    transaction_type: TransactionType
    category: str = Field(min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    frequency: IncomeFrequency | None = None
    date: datetime | None = None

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("frequency", mode="before")
    @classmethod
    def normalize_frequency_value(cls, value):
        return normalize_frequency(value)

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
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    transaction_type: str
    category: str
    description: str | None
    frequency: str | None = None
    date: datetime
    user_id: int


class TransactionUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    transaction_type: TransactionType | None = None
    category: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    frequency: IncomeFrequency | None = None
    date: datetime | None = None

    @field_validator("transaction_type", mode="before")
    @classmethod
    def normalize_transaction_type(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("frequency", mode="before")
    @classmethod
    def normalize_frequency_value(cls, value):
        return normalize_frequency(value)

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
