from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.schemas.ai import FinanceQuestion
from app.services.auth import get_current_user
from app.services.ai import answer_finance_question, generate_financial_summary

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


@router.post("/", response_model=TransactionResponse)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction_data = transaction.model_dump(exclude_none=True)
    new_transaction = Transaction(
        **transaction_data,
        user_id=current_user.id
    )

    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    return new_transaction


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
        "daily": 30,
        "weekly": 4.33,
        "monthly": 1,
    }

    total_income = 0.0
    monthly_income = 0.0
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

    summary = generate_financial_summary(transactions, total_income, total_expenses)

    return {
        "summary": summary,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "category_breakdown": category_totals,
    }


@router.post("/insights/question")
def ask_financial_assistant(
    question_data: FinanceQuestion,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    total_income = sum(t.amount for t in transactions if t.transaction_type == "income")
    total_expenses = sum(t.amount for t in transactions if t.transaction_type == "expense")

    answer = answer_finance_question(
        question_data.question,
        transactions,
        total_income,
        total_expenses
    )

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
