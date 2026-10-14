from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user
from app.services.analytics import get_monthly_summary
from app.services.predictions import (
    budget_risks,
    detect_anomalies,
    forecast_month_end,
    savings_target,
)
router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/monthly")
def monthly_analytics(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    year = year or now.year
    month = month or now.month

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    current = get_monthly_summary(db, current_user.id, year, month)
    previous = get_monthly_summary(db, current_user.id, prev_year, prev_month)

    if previous["expenses"]:
        change = round(
            (current["expenses"] - previous["expenses"]) / previous["expenses"] * 100, 1
        )
    else:
        change = None

    return {
        "current": current,
        "previous": previous,
        "expense_change_percent": change,
    }

@router.get("/trend")
def spending_trend(
    months: int = Query(default=6, ge=2, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Income, expenses and savings for each of the last N months (oldest first)."""
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    points = []

    for _ in range(months):
        summary = get_monthly_summary(db, current_user.id, year, month)
        points.append(
            {
                "month": summary["month"],
                "income": summary["income"],
                "expenses": summary["expenses"],
                "net_savings": summary["net_savings"],
            }
        )
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1

    points.reverse()
    return points

@router.get("/predictions")
def predictions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Forecast, unusual spending, budget risk and a savings target in one call."""
    return {
        "forecast": forecast_month_end(db, current_user.id),
        "unusual_spending": detect_anomalies(db, current_user.id),
        "budget_risks": budget_risks(db, current_user.id),
        "savings_target": savings_target(db, current_user.id),
    }