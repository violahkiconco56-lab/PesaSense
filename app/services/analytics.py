from datetime import datetime

from sqlalchemy.orm import Session

from app.models.transaction import Transaction


def month_range(year: int, month: int):
    """Return (start of month, start of next month)."""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def get_monthly_summary(db: Session, user_id: int, year: int, month: int) -> dict:
    start, end = month_range(year, month)

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.date >= start,
            Transaction.date < end,
        )
        .all()
    )

    income = 0.0
    expenses = 0.0
    category_totals = {}

    for t in transactions:
        kind = (t.transaction_type or "").lower()
        if kind == "income":
            income += t.amount
        elif kind == "expense":
            expenses += t.amount
            name = (t.category or "Other").title()
            category_totals[name] = category_totals.get(name, 0) + t.amount

    net_savings = income - expenses
    savings_rate = round(net_savings / income * 100, 1) if income else None

    category_breakdown = [
        {
            "category": name,
            "total": total,
            "percent": round(total / expenses * 100, 1) if expenses else 0,
        }
        for name, total in sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        )
    ]

    return {
        "month": f"{year}-{month:02d}",
        "income": income,
        "expenses": expenses,
        "net_savings": net_savings,
        "savings_rate": savings_rate,
        "category_breakdown": category_breakdown,
        "transaction_count": len(transactions),
    }