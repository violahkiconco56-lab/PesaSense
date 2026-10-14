import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation

from app.config import settings


REQUIRED_HEADERS = {"date", "description", "amount", "transaction_type"}
OPTIONAL_HEADERS = {"category"}
AMOUNT_PATTERN = re.compile(r"^[0-9]{1,16}(?:\.[0-9]{1,8})?$")


class CsvStatementError(ValueError):
    pass


@dataclass
class ParsedStatementRow:
    line_number: int
    date: datetime | None
    description: str | None
    amount: Decimal | None
    transaction_type: str | None
    category: str | None
    errors: list[str]
    fingerprint: str | None = None


def _parse_date(value: str) -> datetime:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError
    try:
        parsed_date = date.fromisoformat(cleaned)
    except ValueError:
        parsed_date = None
    if parsed_date is not None:
        return datetime.combine(parsed_date, time.min, tzinfo=timezone.utc)

    parsed_datetime = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    if parsed_datetime.tzinfo is None:
        parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
    return parsed_datetime.astimezone(timezone.utc)


def _canonical_description(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.split()).casefold()


def _fingerprint(row: ParsedStatementRow, occurrence: int) -> str:
    canonical = [
        row.date.isoformat() if row.date else "",
        _canonical_description(row.description),
        format(row.amount.normalize(), "f") if row.amount is not None else "",
        row.transaction_type or "",
        _canonical_description(row.category or "Other"),
        occurrence,
    ]
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def parse_csv_statement(content: bytes) -> list[ParsedStatementRow]:
    """Parse the documented UTF-8 CSV format without retaining the source file."""
    if len(content) > settings.CSV_IMPORT_MAX_BYTES:
        raise CsvStatementError("The CSV file exceeds the upload size limit.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvStatementError("The CSV must use UTF-8 encoding.") from exc
    if "\x00" in text:
        raise CsvStatementError("The CSV contains invalid binary data.")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise CsvStatementError("The CSV file is empty.") from exc
    except csv.Error as exc:
        raise CsvStatementError("The CSV header is malformed.") from exc

    normalized_headers = [header.strip().lower() for header in headers]
    if len(normalized_headers) != len(set(normalized_headers)):
        raise CsvStatementError("The CSV contains duplicate column names.")
    header_set = set(normalized_headers)
    if not REQUIRED_HEADERS.issubset(header_set):
        missing = ", ".join(sorted(REQUIRED_HEADERS - header_set))
        raise CsvStatementError(f"Missing required columns: {missing}.")
    if header_set - REQUIRED_HEADERS - OPTIONAL_HEADERS:
        raise CsvStatementError(
            "Unsupported columns found. Use the documented CSV column names."
        )
    if len(normalized_headers) != len(header_set):
        raise CsvStatementError("The CSV contains invalid column names.")

    positions = {name: index for index, name in enumerate(normalized_headers)}
    parsed_rows: list[ParsedStatementRow] = []
    occurrence_counts: dict[tuple, int] = defaultdict(int)
    record_count = 0

    try:
        for fields in reader:
            record_count += 1
            if record_count > settings.CSV_IMPORT_MAX_ROWS:
                raise CsvStatementError("The CSV exceeds the maximum row count.")
            if not fields or all(not field.strip() for field in fields):
                continue

            line_number = reader.line_num
            errors: list[str] = []
            if len(fields) != len(normalized_headers):
                parsed_rows.append(
                    ParsedStatementRow(
                        line_number, None, None, None, None, None,
                        ["The row does not match the header column count."],
                    )
                )
                continue

            raw_date = fields[positions["date"]].strip()
            raw_description = fields[positions["description"]].strip()
            raw_amount = fields[positions["amount"]].strip()
            raw_type = fields[positions["transaction_type"]].strip().lower()
            raw_category = (
                fields[positions["category"]].strip()
                if "category" in positions
                else ""
            )

            try:
                parsed_date = _parse_date(raw_date)
            except ValueError:
                parsed_date = None
                errors.append("Enter a valid ISO date or date-time.")

            if len(raw_description) > 255:
                description = None
                errors.append("Description must be 255 characters or fewer.")
            else:
                description = raw_description or None

            amount = None
            if not AMOUNT_PATTERN.fullmatch(raw_amount):
                errors.append("Amount must be positive decimal digits with up to 8 decimals.")
            else:
                try:
                    amount = Decimal(raw_amount)
                    if amount <= 0 or not amount.is_finite():
                        amount = None
                        errors.append("Amount must be greater than zero.")
                except InvalidOperation:
                    errors.append("Enter a valid decimal amount.")

            transaction_type = (
                raw_type
                if raw_type in {"income", "expense", "transfer"}
                else None
            )
            if raw_type == "transfer":
                errors.append("Transfers are not supported and need review.")
            elif transaction_type is None:
                errors.append("Transaction type must be income or expense.")

            category = (raw_category or "Other").title()
            if len(category) < 2 or len(category) > 50:
                errors.append("Category must be between 2 and 50 characters.")

            row = ParsedStatementRow(
                line_number=line_number,
                date=parsed_date,
                description=description,
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                errors=errors,
            )
            if not errors:
                signature = (
                    parsed_date.isoformat(),
                    _canonical_description(description),
                    format(amount.normalize(), "f"),
                    transaction_type,
                    _canonical_description(category),
                )
                occurrence_counts[signature] += 1
                row.fingerprint = _fingerprint(row, occurrence_counts[signature])
            parsed_rows.append(row)
    except csv.Error as exc:
        raise CsvStatementError("The CSV contains malformed quoting or fields.") from exc

    if not parsed_rows:
        raise CsvStatementError("The CSV contains no transaction rows.")
    return parsed_rows
