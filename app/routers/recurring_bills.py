import calendar
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.recurring_bill import RecurringBill
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.recurring_bill import (
    RecurringBillCreate,
    RecurringBillResponse,
    RecurringBillUpdate,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/recurring-bills", tags=["Recurring Bills"])


def add_period(date: datetime, frequency: str) -> datetime:
    """Move a due date forward by one billing period."""
    if frequency == "weekly":
        return date + timedelta(days=7)

    if frequency == "yearly":
        months = 12
    else:
        months = 1

    month_index = date.month - 1 + months
    year = date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)


def naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_bill_response(bill: RecurringBill) -> RecurringBillResponse:
    response = RecurringBillResponse.model_validate(bill)
    due = bill.next_due_date.replace(tzinfo=None)
    response.days_until_due = (due.date() - naive_now().date()).days
    response.is_overdue = bool(bill.is_active and response.days_until_due < 0)
    return response


def get_user_bill(db: Session, bill_id: int, user_id: int) -> RecurringBill:
    bill = (
        db.query(RecurringBill)
        .filter(RecurringBill.id == bill_id, RecurringBill.user_id == user_id)
        .first()
    )
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recurring bill not found"
        )
    return bill


@router.post("/", response_model=RecurringBillResponse)
def create_bill(
    data: RecurringBillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bill_data = data.model_dump()
    bill_data["next_due_date"] = bill_data["next_due_date"].replace(tzinfo=None)
    bill = RecurringBill(**bill_data, user_id=current_user.id)
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return build_bill_response(bill)


@router.get("/", response_model=list[RecurringBillResponse])
def list_bills(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bills = (
        db.query(RecurringBill)
        .filter(RecurringBill.user_id == current_user.id)
        .order_by(RecurringBill.next_due_date.asc())
        .all()
    )
    return [build_bill_response(bill) for bill in bills]


@router.get("/upcoming", response_model=list[RecurringBillResponse])
def upcoming_bills(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Active bills due within the next N days, including overdue ones."""
    cutoff = naive_now() + timedelta(days=days)
    bills = (
        db.query(RecurringBill)
        .filter(
            RecurringBill.user_id == current_user.id,
            RecurringBill.is_active.is_(True),
            RecurringBill.next_due_date <= cutoff,
        )
        .order_by(RecurringBill.next_due_date.asc())
        .all()
    )
    return [build_bill_response(bill) for bill in bills]


@router.put("/{bill_id}", response_model=RecurringBillResponse)
def update_bill(
    bill_id: int,
    data: RecurringBillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bill = get_user_bill(db, bill_id, current_user.id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "next_due_date" and value is not None:
            value = value.replace(tzinfo=None)
        setattr(bill, field, value)
    db.commit()
    db.refresh(bill)
    return build_bill_response(bill)


@router.post("/{bill_id}/pay", response_model=RecurringBillResponse)
def mark_bill_paid(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record the payment as an expense and move the due date forward."""
    bill = get_user_bill(db, bill_id, current_user.id)

    expense = Transaction(
        amount=bill.amount,
        transaction_type="expense",
        category=bill.category,
        description=f"{bill.name} (recurring bill)",
        user_id=current_user.id,
    )
    db.add(expense)

    bill.next_due_date = add_period(bill.next_due_date, bill.frequency)

    db.commit()
    db.refresh(bill)
    return build_bill_response(bill)


@router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bill = get_user_bill(db, bill_id, current_user.id)
    db.delete(bill)
    db.commit()