from pydantic import BaseModel, Field


class FinanceQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=500)
