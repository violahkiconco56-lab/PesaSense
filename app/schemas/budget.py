from pydantic import BaseModel


class BudgetCreate(BaseModel):
    category: str
    limit_amount: float
    month: int
    year: int


class BudgetUpdate(BaseModel):
    category: str | None = None
    limit_amount: float | None = None
    month: int | None = None
    year: int | None = None


class BudgetResponse(BaseModel):
    id: int
    category: str
    limit_amount: float
    month: int
    year: int
    user_id: int

    class Config:
        from_attributes = True