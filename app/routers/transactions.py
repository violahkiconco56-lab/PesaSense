from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.financial_account import FinancialAccount
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.schemas.transaction_import import (
    TransactionImportPreview,
    TransactionImportResult,
)
from app.schemas.ai import FinanceQuestion
from app.services.auth import get_current_user
from app.services.ai import (
    AIServiceError,
    answer_finance_question,
    generate_financial_summary,
)
from app.services.financial_intelligence import (
    build_financial_intelligence,
    llm_financial_context,
)
from app.services.csv_statement_import import (
    CsvStatementError,
    ParsedStatementRow,
    parse_csv_statement,
)

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


def _owned_account(db: Session, account_id: int, user_id: int) -> FinancialAccount:
    account = (
        db.query(FinancialAccount)
        .filter(
            FinancialAccount.id == account_id,
            FinancialAccount.user_id == user_id,
        )
        .first()
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )
    return account


async def _read_csv(file: UploadFile) -> bytes:
    content = await file.read(settings.CSV_IMPORT_MAX_BYTES + 1)
    if len(content) > settings.CSV_IMPORT_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The CSV file exceeds the upload size limit.",
        )
    return content


def _row_status(row: ParsedStatementRow, existing_fingerprints: set[str]) -> str:
    if row.errors:
        return "invalid"
    if row.fingerprint in existing_fingerprints:
        return "duplicate"
    return "valid"


def _preview_response(
    account: FinancialAccount,
    rows: list[ParsedStatementRow],
    existing_fingerprints: set[str],
) -> TransactionImportPreview:
    response_rows = []
    importable_count = duplicate_count = invalid_count = 0
    for row in rows:
        row_status = _row_status(row, existing_fingerprints)
        if row_status == "valid":
            importable_count += 1
        elif row_status == "duplicate":
            duplicate_count += 1
        else:
            invalid_count += 1
        response_rows.append(
            {
                "line_number": row.line_number,
                "status": row_status,
                "errors": row.errors,
                "date": row.date,
                "description": row.description,
                "transaction_type": row.transaction_type,
                "amount": format(row.amount, "f") if row.amount is not None else None,
                "category": row.category,
            }
        )
    return TransactionImportPreview(
        account_id=account.id,
        account_name=account.name,
        currency=account.currency,
        total_rows=len(rows),
        importable_count=importable_count,
        duplicate_count=duplicate_count,
        invalid_count=invalid_count,
        rows=response_rows,
    )


def _existing_fingerprints(
    db: Session, account_id: int, fingerprints: set[str]
) -> set[str]:
    if not fingerprints:
        return set()
    return set(
        fingerprint
        for (fingerprint,) in db.query(Transaction.import_fingerprint)
        .filter(
            Transaction.account_id == account_id,
            Transaction.import_fingerprint.in_(fingerprints),
        )
        .all()
    )


@router.post("/", response_model=TransactionResponse)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction_data = transaction.model_dump(exclude_none=True)
    account_id = transaction_data.get("account_id")
    if account_id is not None:
        _owned_account(db, account_id, current_user.id)
    new_transaction = Transaction(
        **transaction_data,
        user_id=current_user.id
    )

    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    return new_transaction


@router.post("/import/preview", response_model=TransactionImportPreview)
async def preview_transaction_import(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = _owned_account(db, account_id, current_user.id)
    try:
        rows = parse_csv_statement(await _read_csv(file))
    except CsvStatementError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    fingerprints = {row.fingerprint for row in rows if row.fingerprint}
    existing = _existing_fingerprints(db, account.id, fingerprints)
    return _preview_response(account, rows, existing)


@router.post("/import", response_model=TransactionImportResult)
async def import_transactions(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = _owned_account(db, account_id, current_user.id)
    try:
        rows = parse_csv_statement(await _read_csv(file))
    except CsvStatementError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    fingerprints = {row.fingerprint for row in rows if row.fingerprint}
    existing = _existing_fingerprints(db, account.id, fingerprints)
    imported_count = skipped_duplicate_count = rejected_count = 0
    try:
        for row in rows:
            if row.errors:
                rejected_count += 1
                continue
            if row.fingerprint in existing:
                skipped_duplicate_count += 1
                continue

            transaction = Transaction(
                amount=row.amount,
                transaction_type=row.transaction_type,
                category=row.category,
                description=row.description,
                frequency="one_time" if row.transaction_type == "income" else None,
                date=row.date,
                user_id=current_user.id,
                account_id=account.id,
                import_fingerprint=row.fingerprint,
            )
            db.add(transaction)
            existing.add(row.fingerprint)
            imported_count += 1
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        error_text = str(exc.orig).lower()
        is_import_duplicate = (
            "uq_transactions_account_import_fingerprint" in error_text
            or (
                "unique constraint failed" in error_text
                and "transactions.account_id" in error_text
                and "transactions.import_fingerprint" in error_text
            )
        )
        if is_import_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The statement changed during import. Preview it again before confirming.",
            ) from exc
        raise
    except Exception:
        db.rollback()
        raise

    return TransactionImportResult(
        imported_count=imported_count,
        skipped_duplicate_count=skipped_duplicate_count,
        rejected_count=rejected_count,
    )


@router.get("/", response_model=list[TransactionResponse])
def get_transactions(
    transaction_type: Literal["income", "expense"] | None = Query(default=None),
    category: str | None = Query(default=None, min_length=2, max_length=50),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    min_amount: float | None = Query(default=None, gt=0),
    max_amount: float | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_amount cannot be greater than max_amount"
        )

    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from cannot be later than date_to"
        )

    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)

    if category:
        query = query.filter(Transaction.category.ilike(f"%{category.strip()}%"))

    if date_from:
        query = query.filter(Transaction.date >= date_from)

    if date_to:
        query = query.filter(Transaction.date <= date_to)

    if min_amount is not None:
        query = query.filter(Transaction.amount >= min_amount)

    if max_amount is not None:
        query = query.filter(Transaction.amount <= max_amount)

    if search:
        query = query.filter(Transaction.description.ilike(f"%{search.strip()}%"))

    return (
        query
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/dashboard/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .all()
    )

    total_income = sum(t.amount for t in transactions if t.transaction_type.lower() == "income")
    total_expenses = sum(t.amount for t in transactions if t.transaction_type.lower() == "expense")
    balance = total_income - total_expenses

    category_totals = {}
    for t in transactions:
        if t.transaction_type.lower() == "expense":
            category_totals[t.category] = category_totals.get(t.category, 0) + t.amount

    top_category = max(category_totals, key=category_totals.get) if category_totals else None

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "highest_expense_category": top_category,
        "recent_transactions": sorted(
            transactions,
            key=lambda transaction: transaction.date,
            reverse=True
        )[:5]
    }


@router.get("/income/summary")
def get_income_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Summarise income sources, including recurring ones.

    Recurring income is converted to a monthly equivalent so the dashboard and
    the AI assistant can reason about steady earnings, not just cash logged.
    """
    incomes = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == "income",
        )
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .all()
    )

    monthly_multiplier = {
        "daily": Decimal("30"),
        "weekly": Decimal("4.33"),
        "monthly": Decimal("1"),
    }

    total_income = Decimal("0")
    monthly_income = Decimal("0")
    frequency_breakdown = {}
    source_totals = {}

    for income in incomes:
        total_income += income.amount

        frequency = (income.frequency or "one_time").lower()
        multiplier = monthly_multiplier.get(frequency, 0)
        monthly_income += income.amount * multiplier

        frequency_breakdown[frequency] = frequency_breakdown.get(frequency, 0) + income.amount
        source_label = (income.category or "Other").title()
        source_totals[source_label] = source_totals.get(source_label, 0) + income.amount

    distinct_sources = len(source_totals)

    return {
        "total_income": total_income,
        "monthly_income": round(monthly_income, 2),
        "income_count": len(incomes),
        "distinct_sources": distinct_sources,
        "frequency_breakdown": frequency_breakdown,
        "source_totals": source_totals,
        "average_per_source": round(total_income / distinct_sources, 2) if distinct_sources else 0,
    }


@router.get("/insights/summary")
def get_ai_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = build_financial_intelligence(db, current_user.id)
    try:
        analysis["summary"] = generate_financial_summary(
            llm_financial_context(analysis)
        )
        analysis["ai_available"] = True
    except AIServiceError as exc:
        analysis["ai_available"] = False
        analysis["ai_summary_error"] = exc.message
    return analysis


@router.post("/insights/question")
def ask_financial_assistant(
    question_data: FinanceQuestion,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = build_financial_intelligence(db, current_user.id)
    try:
        answer = answer_finance_question(
            question_data.question,
            llm_financial_context(analysis),
            [message.model_dump() for message in question_data.history],
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {"answer": answer}


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id
        )
        .first()
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    updated_data: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id
        )
        .first()
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    update_fields = updated_data.model_dump(exclude_unset=True)
    account_id = update_fields.get("account_id")
    if account_id is not None:
        _owned_account(db, account_id, current_user.id)
    for field, value in update_fields.items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)

    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id
        )
        .first()
    )

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    db.delete(transaction)
    db.commit()
