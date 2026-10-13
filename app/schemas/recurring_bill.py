from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Frequency = Literal["weekly", "monthly", "yearly"]


class RecurringBillCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    amount: float = Field(gt=0)
    category: str = Field(min_length=2, max_length=50)
    frequency: Frequency = "monthly"
    next_due_date: datetime

    @field_validator("name", "category", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class RecurringBillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    amount: float | None = Field(default=None, gt=0)
    category: str | None = Field(default=None, min_length=2, max_length=50)
    frequency: Frequency | None = None
    next_due_date: datetime | None = None
    is_active: bool | None = None

    @field_validator("name", "category", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class RecurringBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    amount: float
    category: str
    frequency: str
    next_due_date: datetime
    is_active: bool
    created_at: datetime | None

    # Calculated in the router
    days_until_due: int = 0
    is_overdue: bool = False