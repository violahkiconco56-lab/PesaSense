from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


ImportRowStatus = Literal["valid", "duplicate", "invalid"]


class TransactionImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int
    status: ImportRowStatus
    errors: list[str]
    date: datetime | None
    description: str | None
    transaction_type: str | None
    amount: str | None
    category: str | None


class TransactionImportPreview(BaseModel):
    account_id: int
    account_name: str
    currency: str
    total_rows: int
    importable_count: int
    duplicate_count: int
    invalid_count: int
    rows: list[TransactionImportRow]


class TransactionImportResult(BaseModel):
    imported_count: int
    skipped_duplicate_count: int
    rejected_count: int
