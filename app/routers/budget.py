from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.budget import Budget
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetResponse, BudgetUpdate
from app.services.auth import get_current_user

router = APIRouter(
    prefix="/budgets",
    tags=["Budgets"]
)


def get_month_range(month: int, year: int):
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start_date, end_date


def get_budget_spent(db: Session, current_user: User, budget: Budget):
    start_date, end_date = get_month_range(budget.month, budget.year)
    return (
        db.query(func.sum(Transaction.amount))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.category == budget.category,
            Transaction.transaction_type == "expense",
            Transaction.date >= start_date,
            Transaction.date < end_date,
        )
        .scalar() or 0
    )


def build_budget_status(db: Session, current_user: User, budget: Budget):
    spent = get_budget_spent(db, current_user, budget)
    remaining = budget.limit_amount - spent
    used_percentage = round((spent / budget.limit_amount) * 100, 2)
    return {
        "budget_id": budget.id,
        "category": budget.category,
        "month": budget.month,
        "year": budget.year,
        "limit_amount": budget.limit_amount,
        "spent": spent,
        "remaining": remaining,
        "used_percentage": used_percentage,
        "approaching_limit": used_percentage >= 80 and spent <= budget.limit_amount,
        "over_budget": spent > budget.limit_amount
    }


def find_duplicate_budget(
    db: Session,
    current_user: User,
    category: str,
    month: int,
    year: int,
    exclude_budget_id: int | None = None
):
    query = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.category == category,
        Budget.month == month,
        Budget.year == year,
    )
    if exclude_budget_id is not None:
        query = query.filter(Budget.id != exclude_budget_id)
    return query.first()


@router.post("/", response_model=BudgetResponse)
def create_budget(
    budget: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing_budget = find_duplicate_budget(
        db,
        current_user,
        budget.category,
        budget.month,
        budget.year
    )
    if existing_budget:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Budget already exists for this category and month."
        )

    new_budget = Budget(
        category=budget.category,
        limit_amount=budget.limit_amount,
        month=budget.month,
        year=budget.year,
        user_id=current_user.id
    )

    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)

    return new_budget


@router.get("/", response_model=list[BudgetResponse])
def get_budgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return (
        db.query(Budget)
        .filter(Budget.user_id == current_user.id)
        .order_by(Budget.year.desc(), Budget.month.desc(), Budget.category.asc())
        .all()
    )


@router.get("/performance")
def get_budget_performance(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Budget).filter(Budget.user_id == current_user.id)

    if month is not None:
        query = query.filter(Budget.month == month)

    if year is not None:
        query = query.filter(Budget.year == year)

    budgets = query.order_by(Budget.year.desc(), Budget.month.desc(), Budget.category.asc()).all()
    budget_statuses = [
        build_budget_status(db, current_user, budget)
        for budget in budgets
    ]

    total_limit = sum(item["limit_amount"] for item in budget_statuses)
    total_spent = sum(item["spent"] for item in budget_statuses)

    return {
        "total_budgeted": total_limit,
        "total_spent": total_spent,
        "total_remaining": total_limit - total_spent,
        "budgets": budget_statuses
    }


@router.get("/alerts")
def get_budget_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budgets = (
        db.query(Budget)
        .filter(Budget.user_id == current_user.id)
        .all()
    )

    alerts = []
    for budget in budgets:
        status_data = build_budget_status(db, current_user, budget)
        if status_data["over_budget"]:
            alert_type = "over_budget"
            message = f"{budget.category} is over budget for {budget.month}/{budget.year}."
        elif status_data["approaching_limit"]:
            alert_type = "approaching_limit"
            message = f"{budget.category} is close to the budget limit for {budget.month}/{budget.year}."
        else:
            continue

        alerts.append({
            "type": alert_type,
            "message": message,
            **status_data
        })

    return {"alerts": alerts}


@router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: int,
    updated_data: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    update_fields = updated_data.model_dump(exclude_unset=True)
    target_category = update_fields.get("category", budget.category)
    target_month = update_fields.get("month", budget.month)
    target_year = update_fields.get("year", budget.year)
    existing_budget = find_duplicate_budget(
        db,
        current_user,
        target_category,
        target_month,
        target_year,
        exclude_budget_id=budget.id
    )
    if existing_budget:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Budget already exists for this category and month."
        )

    for field, value in update_fields.items():
        setattr(budget, field, value)

    db.commit()
    db.refresh(budget)
    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    db.delete(budget)
    db.commit()


@router.get("/{budget_id}/remaining")
def get_remaining_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    return build_budget_status(db, current_user, budget)
