from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PremiumPaymentRequest(BaseModel):
    msisdn: str = Field(pattern=r"^\+2567\d{8}$")


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference: str
    plan: Literal["premium"]
    amount: float
    currency: str
    status: Literal["pending", "success", "failed"]
    message: str
    current_period_end: datetime | None = None


class PremiumPriceResponse(BaseModel):
    amount: int
    currency: Literal["UGX"]


class RelworxWebhook(BaseModel):
    status: str | None = None
    customer_reference: str | None = None
    internal_reference: str | None = None
