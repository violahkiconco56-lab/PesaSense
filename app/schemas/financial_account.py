from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


FinancialAccountType = Literal[
    "mtn_mobile_money",
    "airtel_money",
    "bank",
    "manual",
]


class FinancialAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)
    account_type: FinancialAccountType
    currency: str = Field(default="UGX", min_length=3, max_length=3)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return value


class FinancialAccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=100)
    account_type: FinancialAccountType | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value):
        if isinstance(value, str):
            return value.strip().upper()
        return value


class FinancialAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    account_type: FinancialAccountType
    currency: str
    created_at: datetime | None
