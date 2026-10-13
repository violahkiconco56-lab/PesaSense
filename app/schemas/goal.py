from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GoalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    target_amount: float = Field(gt=0)
    saved_amount: float = Field(default=0, ge=0)
    deadline: datetime | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    target_amount: float | None = Field(default=None, gt=0)
    saved_amount: float | None = Field(default=None, ge=0)
    deadline: datetime | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class GoalContribution(BaseModel):
    amount: float = Field(gt=0)


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    target_amount: float
    saved_amount: float
    deadline: datetime | None
    created_at: datetime | None

    # Calculated in the router, not stored in the database
    percent_saved: float = 0
    amount_remaining: float = 0
    monthly_needed: float | None = None
    is_completed: bool = False