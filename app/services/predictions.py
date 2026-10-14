import calendar
import statistics
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.transaction import Transaction
from app.services.analytics import get_monthly_summary, month_range


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _expenses_between(db: Session, user_id: int, start: datetime, end: datetime):
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.date >= start,
            Transaction.date < end,
        )
        .all()
    )
    return [
        t
        for t in rows
        if (t.transaction_type or "").lower() == "expense" and t.amount is not None
    ]


def _pace_projection(spent: float, days_elapsed: int, days_in_month: int) -> float:
    return spent / max(days_elapsed, 1) * days_in_month


def forecast_month_end(db: Session, user_id: int) -> dict:
    """Estimate month-end spending using current pace or completed months."""
    now = _now()
    start, end = month_range(now.year, now.month)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_elapsed = max(now.day, 1)

    current_expenses = _expenses_between(db, user_id, start, end)
    spent = sum(t.amount for t in current_expenses)
    income = Decimal(
        str(get_monthly_summary(db, user_id, now.year, now.month)["income"])
    )
    history = []
    history_year, history_month = now.year, now.month
    for _ in range(3):
        if history_month == 1:
            history_year, history_month = history_year - 1, 12
        else:
            history_month -= 1
        monthly = get_monthly_summary(db, user_id, history_year, history_month)
        if monthly["transaction_count"] and monthly["expenses"] > 0:
            history.append(Decimal(str(monthly["expenses"])))

    if spent > 0:
        projected = _pace_projection(spent, days_elapsed, days_in_month)
        method = "current_month_pace"
        confidence = (
            "low"
            if days_elapsed < 7 or len(current_expenses) < 3
            else "medium"
        )
    elif history:
        historical_average = sum(history) / len(history)
        projected = historical_average
        method = "recent_monthly_average"
        confidence = "low" if len(history) == 1 else "medium"
    else:
        projected = None
        method = "insufficient_history"
        confidence = "insufficient_data"

    return {
        "spent_so_far": round(spent, 2),
        "projected_total": round(projected, 2) if projected is not None else None,
        "daily_average": round(spent / days_elapsed, 2),
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "income_this_month": income,
        "projected_savings": (
            round(income - projected, 2) if projected is not None else None
        ),
        "confidence": confidence,
        "is_available": projected is not None,
        "method": method,
        "historical_months_used": len(history),
    }


def detect_anomalies(db: Session, user_id: int) -> list[dict]:
    """Flag this month's expenses far above the usual amount for that category."""
    now = _now()
    start, end = month_range(now.year, now.month)
    history = _expenses_between(db, user_id, start - timedelta(days=90), start)
    current = _expenses_between(db, user_id, start, end)

    amounts_by_category: dict[str, list[Decimal]] = {}
    for t in history:
        key = (t.category or "other").lower()
        amounts_by_category.setdefault(key, []).append(t.amount)

    alerts = []
    for t in current:
        amounts = amounts_by_category.get((t.category or "other").lower(), [])
        if len(amounts) < 4:
            continue  # not enough history to call anything unusual

        mean = statistics.mean(amounts)
        spread = statistics.pstdev(amounts)
        threshold = mean + 2 * spread if spread > 0 else mean * 2

        if t.amount > threshold and t.amount > mean * Decimal("1.5"):
            alerts.append(
                {
                    "transaction_id": t.id,
                    "description": t.description or t.category,
                    "category": (t.category or "Other").title(),
                    "amount": t.amount,
                    "usual_amount": round(mean, 2),
                    "times_higher": float(round(t.amount / mean, 1)),
                    "date": t.date.isoformat() if t.date else None,
                    "baseline_transaction_count": len(amounts),
                    "explanation": (
                        f"This transaction is {t.amount / mean:.1f} times the "
                        f"90-day average of {format(mean, ',.0f')} UGX across "
                        f"{len(amounts)} earlier {t.category or 'other'} expenses."
                    ),
                }
            )

    alerts.sort(key=lambda alert: alert["times_higher"], reverse=True)
    return alerts


def budget_risks(db: Session, user_id: int) -> list[dict]:
    """For each budget this month: on_track, at_risk (will exceed) or exceeded."""
    now = _now()
    start, end = month_range(now.year, now.month)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_elapsed = max(now.day, 1)

    budgets = (
        db.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.month == now.month,
            Budget.year == now.year,
        )
        .all()
    )
    expenses = _expenses_between(db, user_id, start, end)

    results = []
    for budget in budgets:
        spent = sum(
            t.amount
            for t in expenses
            if (t.category or "").lower() == (budget.category or "").lower()
        )
        projected = _pace_projection(spent, days_elapsed, days_in_month)

        limit_amount = Decimal(str(budget.limit_amount))
        if spent > limit_amount:
            status = "exceeded"
        elif projected > limit_amount:
            status = "at_risk"
        else:
            status = "on_track"

        results.append(
            {
                "category": budget.category,
                "limit": limit_amount,
                "spent": round(spent, 2),
                "projected": round(projected, 2),
                "percent_used": float(
                    round(spent / limit_amount * Decimal("100"), 1)
                )
                if limit_amount
                else 0,
                "status": status,
            }
        )

    order = {"exceeded": 0, "at_risk": 1, "on_track": 2}
    results.sort(key=lambda item: order[item["status"]])
    return results


def savings_target(db: Session, user_id: int) -> dict:
    """Suggest a realistic monthly savings amount from the last 3 months."""
    now = _now()
    year, month = now.year, now.month
    surpluses = []

    for _ in range(3):
        if month == 1:
            year, month = year - 1, 12
        else:
            month -= 1
        summary = get_monthly_summary(db, user_id, year, month)
        if summary["income"] > 0 or summary["expenses"] > 0:
            surpluses.append(summary["net_savings"])

    if not surpluses:
        return {
            "months_used": 0,
            "average_surplus": 0,
            "recommended_monthly_saving": 0,
            "message": "Not enough history yet. Add a full month of transactions.",
        }

    average = sum(surpluses) / len(surpluses)
    if average <= 0:
        return {
            "months_used": len(surpluses),
            "average_surplus": round(average, 2),
            "recommended_monthly_saving": 0,
            "message": "You spent about as much as you earned. Reduce spending before setting a target.",
        }

    # Suggest 70% of the usual surplus, rounded to the nearest UGX 5,000
    recommended = round(average * Decimal("0.7") / Decimal("5000")) * 5000
    return {
        "months_used": len(surpluses),
        "average_surplus": round(average, 2),
        "recommended_monthly_saving": recommended,
        "message": f"Based on your last {len(surpluses)} month(s), saving this much is realistic.",
    }