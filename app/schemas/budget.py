from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


CURRENT_YEAR = datetime.now().year


class BudgetCreate(BaseModel):
    category: str = Field(min_length=2, max_length=50)
    limit_amount: float = Field(gt=0)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=CURRENT_YEAR + 10)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        if isinstance(value, str):
            return value.strip().title()
        return value


class BudgetUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=2, max_length=50)
    limit_amount: float | None = Field(default=None, gt=0)
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=2000, le=CURRENT_YEAR + 10)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        if isinstance(value, str):
            return value.strip().title()
        return value


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    limit_amount: float
    month: int
    year: int
    user_id: int

