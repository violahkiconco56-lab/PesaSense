from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


Period = Literal["daily", "weekly", "monthly", "yearly"]


def get_day_range(report_date: date):
    start_date = datetime.combine(report_date, datetime.min.time(), tzinfo=timezone.utc)
    end_date = start_date + timedelta(days=1)
    return start_date, end_date


def get_week_range(report_date: date):
    start_day = report_date - timedelta(days=report_date.weekday())
    start_date = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
    end_date = start_date + timedelta(days=7)
    return start_date, end_date


def get_month_range(month: int, year: int):
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start_date, end_date


def get_year_range(year: int):
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return start_date, end_date


def get_period_range(
    period: Period,
    report_date: date,
    month: int | None,
    year: int | None
):
    selected_year = year or report_date.year
    if period == "daily":
        return get_day_range(report_date)
    if period == "weekly":
        return get_week_range(report_date)
    if period == "monthly":
        return get_month_range(month or report_date.month, selected_year)
    return get_year_range(selected_year)


def get_transactions_for_range(
    db: Session,
    current_user: User,
    start_date: datetime,
    end_date: datetime,
    transaction_type: str | None = None
):
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= start_date,
        Transaction.date < end_date,
    )
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)

    return query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()


def build_report(transactions: list[Transaction], start_date: datetime, end_date: datetime):
    total_income = sum(
        transaction.amount
        for transaction in transactions
        if transaction.transaction_type == "income"
    )
    total_expenses = sum(
        transaction.amount
        for transaction in transactions
        if transaction.transaction_type == "expense"
    )

    category_totals = {}
    for transaction in transactions:
        if transaction.transaction_type != "expense":
            continue
        category_totals[transaction.category] = (
            category_totals.get(transaction.category, 0) + transaction.amount
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "transaction_count": len(transactions),
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": total_income - total_expenses,
        "category_breakdown": category_totals,
        "transactions": transactions
    }


@router.get("/summary")
def get_summary_report(
    period: Period = Query(default="monthly"),
    report_date: date = Query(default_factory=date.today),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_period_range(period, report_date, month, year)
    transactions = get_transactions_for_range(db, current_user, start_date, end_date)
    return {
        "period": period,
        **build_report(transactions, start_date, end_date)
    }


@router.get("/daily")
def get_daily_report(
    report_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_day_range(report_date)
    transactions = get_transactions_for_range(db, current_user, start_date, end_date)
    return build_report(transactions, start_date, end_date)


@router.get("/weekly")
def get_weekly_report(
    report_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_week_range(report_date)
    transactions = get_transactions_for_range(db, current_user, start_date, end_date)
    return build_report(transactions, start_date, end_date)


@router.get("/monthly")
def get_monthly_report(
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_month_range(month, year)
    transactions = get_transactions_for_range(db, current_user, start_date, end_date)
    return build_report(transactions, start_date, end_date)


@router.get("/yearly")
def get_yearly_report(
    year: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_year_range(year)
    transactions = get_transactions_for_range(db, current_user, start_date, end_date)
    return build_report(transactions, start_date, end_date)


@router.get("/income")
def get_income_report(
    period: Period = Query(default="monthly"),
    report_date: date = Query(default_factory=date.today),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_period_range(period, report_date, month, year)
    transactions = get_transactions_for_range(
        db,
        current_user,
        start_date,
        end_date,
        transaction_type="income"
    )
    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "total_income": sum(transaction.amount for transaction in transactions),
        "transaction_count": len(transactions),
        "transactions": transactions
    }


@router.get("/expenses")
def get_expense_report(
    period: Period = Query(default="monthly"),
    report_date: date = Query(default_factory=date.today),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_period_range(period, report_date, month, year)
    transactions = get_transactions_for_range(
        db,
        current_user,
        start_date,
        end_date,
        transaction_type="expense"
    )
    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "total_expenses": sum(transaction.amount for transaction in transactions),
        "transaction_count": len(transactions),
        "transactions": transactions
    }


@router.get("/categories")
def get_category_report(
    period: Period = Query(default="monthly"),
    report_date: date = Query(default_factory=date.today),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_date, end_date = get_period_range(period, report_date, month, year)
    transactions = get_transactions_for_range(
        db,
        current_user,
        start_date,
        end_date,
        transaction_type="expense"
    )
    category_totals = {}
    for transaction in transactions:
        category_totals[transaction.category] = (
            category_totals.get(transaction.category, 0) + transaction.amount
        )

    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "category_breakdown": category_totals
    }
