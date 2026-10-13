from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user
from app.services.analytics import get_monthly_summary

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