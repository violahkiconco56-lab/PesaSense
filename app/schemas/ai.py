from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FinanceConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Conversation messages cannot be empty.")
        return value


class FinanceQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    history: list[FinanceConversationMessage] = Field(
        default_factory=list, max_length=8
    )

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Question must contain at least 5 non-space characters.")
        return value
