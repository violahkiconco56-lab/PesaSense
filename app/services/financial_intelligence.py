import calendar
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.models.goal import Goal
from app.models.recurring_bill import RecurringBill
from app.models.transaction import Transaction
from app.services.analytics import get_monthly_summary, month_range
from app.services.predictions import (
    budget_risks,
    detect_anomalies,
    forecast_month_end,
    savings_target,
)


def _month_before(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _goal_progress(goal: Goal, now: datetime) -> dict:
    target = float(goal.target_amount or 0)
    saved = float(goal.saved_amount or 0)
    remaining = max(target - saved, 0)
    deadline = goal.deadline
    monthly_needed = None

    if deadline and deadline.replace(tzinfo=None) >= now and remaining > 0:
        months_left = max((deadline.replace(tzinfo=None) - now).days / 30.44, 1)
        monthly_needed = round(remaining / months_left, 2)

    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": target,
        "saved_amount": saved,
        "deadline": deadline.isoformat() if deadline else None,
        "amount_remaining": remaining,
        "percent_saved": round(min(saved / target * 100, 100), 1) if target else 0,
        "monthly_needed": monthly_needed,
        "is_completed": remaining == 0,
    }


def _upcoming_bills(db: Session, user_id: int, now: datetime) -> list[dict]:
    cutoff = now + timedelta(days=30)
    bills = (
        db.query(RecurringBill)
        .filter(
            RecurringBill.user_id == user_id,
            RecurringBill.is_active.is_(True),
            RecurringBill.next_due_date <= cutoff,
        )
        .order_by(RecurringBill.next_due_date.asc())
        .limit(8)
        .all()
    )
    return [
        {
            "name": bill.name,
            "category": bill.category,
            "amount": float(bill.amount or 0),
            "frequency": bill.frequency,
            "next_due_date": bill.next_due_date.isoformat(),
            "is_overdue": bill.next_due_date.replace(tzinfo=None) < now,
        }
        for bill in bills
    ]


def _recommendations(
    monthly: dict,
    previous: dict,
    forecast: dict,
    risks: list[dict],
    goals: list[dict],
    bills: list[dict],
    saving_target: dict,
) -> list[dict]:
    recommendations = []

    for risk in risks:
        if risk["status"] == "exceeded":
            recommendations.append(
                {
                    "urgency": "high",
                    "title": f"Review the {risk['category']} budget",
                    "detail": (
                        f"{risk['category']} spending is {risk['percent_used']}% of its "
                        f"{risk['limit']:,.0f} UGX limit. Recorded spending is "
                        f"{risk['spent']:,.0f} UGX."
                    ),
                    "evidence": "Current-month recorded spending exceeds the budget limit.",
                    "estimated_impact": None,
                }
            )
        elif risk["status"] == "at_risk":
            projected_overrun = max(risk["projected"] - risk["limit"], 0)
            recommendations.append(
                {
                    "urgency": "high",
                    "title": f"Keep an eye on the {risk['category']} budget",
                    "detail": (
                        f"At the current spending pace, this budget is projected to exceed "
                        f"its limit by about {projected_overrun:,.0f} UGX."
                    ),
                    "evidence": (
                        f"{risk['percent_used']}% of the limit has been used so far; "
                        "projection extends the current pace through month-end."
                    ),
                    "estimated_impact": round(projected_overrun, 2),
                }
            )

    categories = monthly.get("category_breakdown", [])
    if categories:
        top = categories[0]
        previous_categories = {
            category["category"].casefold(): category["total"]
            for category in previous.get("category_breakdown", [])
        }
        previous_total = previous_categories.get(top["category"].casefold())
        if previous_total and top["total"] > previous_total:
            change = round((top["total"] - previous_total) / previous_total * 100, 1)
            category_detail = (
                f"{top['category']} increased {change}% compared with last month, "
                f"from {previous_total:,.0f} UGX to {top['total']:,.0f} UGX."
            )
            category_evidence = (
                "Compared with the previous month and ranked as the largest "
                "current-month expense category."
            )
        else:
            category_detail = (
                f"{top['category']} is your largest recorded expense category this "
                f"month at {top['percent']}% of expenses."
            )
            category_evidence = f"Recorded spending: {top['total']:,.0f} UGX this month."
        recommendations.append(
            {
                "urgency": "medium",
                "title": f"Review spending in {top['category']}",
                "detail": category_detail,
                "evidence": category_evidence,
                "estimated_impact": None,
            }
        )

    for goal in goals:
        if not goal["is_completed"] and goal["monthly_needed"] is not None:
            recommendations.append(
                {
                    "urgency": "medium",
                    "title": f"Plan a contribution toward {goal['name']}",
                    "detail": (
                        f"Saving about {goal['monthly_needed']:,.0f} UGX per month would "
                        "meet the target by its deadline, based on the time remaining."
                    ),
                    "evidence": (
                        f"{goal['amount_remaining']:,.0f} UGX remains; target date "
                        f"{goal['deadline'][:10]}."
                    ),
                    "estimated_impact": goal["monthly_needed"],
                }
            )

    if bills:
        due_total = sum(bill["amount"] for bill in bills)
        recommendations.append(
            {
                "urgency": "medium",
                "title": "Plan for upcoming recurring bills",
                "detail": (
                    f"Set aside up to {due_total:,.0f} UGX for the active bills due or "
                    "overdue within the next 30 days."
                ),
                "evidence": f"{len(bills)} active bill(s) fall within that date window.",
                "estimated_impact": due_total,
            }
        )

    suggested_saving = float(saving_target.get("recommended_monthly_saving") or 0)
    if suggested_saving > 0:
        recommendations.append(
            {
                "urgency": "low",
                "title": "Consider a realistic monthly savings target",
                "detail": (
                    f"Recent recorded surplus supports considering a target near "
                    f"{suggested_saving:,.0f} UGX per month."
                ),
                "evidence": saving_target.get("message", ""),
                "estimated_impact": suggested_saving,
            }
        )

    if monthly["net_savings"] < 0:
        recommendations.append(
            {
                "urgency": "high",
                "title": "Review this month's cash flow",
                "detail": (
                    "Recorded expenses are currently higher than recorded income this "
                    "month. Review upcoming discretionary spending before adding a new "
                    "savings commitment."
                ),
                "evidence": (
                    f"Income {monthly['income']:,.0f} UGX; expenses "
                    f"{monthly['expenses']:,.0f} UGX month to date."
                ),
                "estimated_impact": None,
            }
        )

    urgency_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(
        key=lambda item: (
            urgency_order[item["urgency"]],
            -(item["estimated_impact"] or 0),
        )
    )
    return recommendations[:6]


def build_financial_intelligence(db: Session, user_id: int) -> dict:
    """Build verified, user-scoped financial metrics without calling an LLM."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    year, month = now.year, now.month
    current = get_monthly_summary(db, user_id, year, month)

    previous_year, previous_month = _month_before(year, month)
    previous = get_monthly_summary(db, user_id, previous_year, previous_month)

    trend = []
    trend_year, trend_month = year, month
    for _ in range(6):
        trend.append(get_monthly_summary(db, user_id, trend_year, trend_month))
        trend_year, trend_month = _month_before(trend_year, trend_month)
    trend.reverse()

    aggregate_rows = (
        db.query(
            func.lower(Transaction.transaction_type),
            func.coalesce(func.sum(Transaction.amount), 0),
            func.count(Transaction.id),
        )
        .filter(Transaction.user_id == user_id)
        .group_by(func.lower(Transaction.transaction_type))
        .all()
    )
    all_time_totals = {
        kind: {"amount": float(amount or 0), "count": int(count)}
        for kind, amount, count in aggregate_rows
    }
    transaction_count = sum(row["count"] for row in all_time_totals.values())
    total_income = all_time_totals.get("income", {}).get("amount", 0)
    total_expenses = all_time_totals.get("expense", {}).get("amount", 0)

    all_time_categories = (
        db.query(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .filter(
            Transaction.user_id == user_id,
            func.lower(Transaction.transaction_type) == "expense",
        )
        .group_by(Transaction.category)
        .all()
    )
    category_breakdown = {
        (category or "Other"): float(amount or 0)
        for category, amount in all_time_categories
    }
    top_expense_category = (
        max(category_breakdown, key=category_breakdown.get)
        if category_breakdown
        else None
    )

    income_rows = (
        db.query(Transaction.amount, Transaction.frequency)
        .filter(
            Transaction.user_id == user_id,
            func.lower(Transaction.transaction_type) == "income",
        )
        .all()
    )
    monthly_multipliers = {"daily": 30, "weekly": 4.33, "monthly": 1}
    monthly_income = sum(
        float(amount or 0)
        * monthly_multipliers.get((frequency or "one_time").lower(), 0)
        for amount, frequency in income_rows
    )

    forecast = forecast_month_end(db, user_id)
    risks = budget_risks(db, user_id)
    anomalies = detect_anomalies(db, user_id)
    saving_target = savings_target(db, user_id)

    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id)
        .order_by(Goal.created_at.desc())
        .limit(10)
        .all()
    )
    goal_progress = [_goal_progress(goal, now) for goal in goals]
    bills = _upcoming_bills(db, user_id, now)
    recommendations = _recommendations(
        current, previous, forecast, risks, goal_progress, bills, saving_target
    )

    budget_summaries = [
        {
            "category": risk["category"],
            "month": month,
            "year": year,
            "limit_amount": risk["limit"],
            "spent": risk["spent"],
            "remaining": risk["limit"] - risk["spent"],
            "used_percentage": risk["percent_used"],
            "over_budget": risk["status"] == "exceeded",
            "status": risk["status"],
            "projected": risk["projected"],
        }
        for risk in risks
    ]

    return {
        "summary": None,
        "ai_summary_error": None,
        "transaction_count": transaction_count,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": total_income - total_expenses,
        "category_breakdown": category_breakdown,
        "top_expense_category": top_expense_category,
        "savings_rate": round(
            (total_income - total_expenses) / total_income * 100, 2
        )
        if total_income
        else None,
        "monthly_income": round(monthly_income, 2),
        "budgets": budget_summaries,
        "period": {
            "month": current["month"],
            "label": now.strftime("%B %Y"),
            "days_elapsed": now.day,
            "days_in_month": calendar.monthrange(year, month)[1],
        },
        "monthly_summary": current,
        "previous_month": previous,
        "monthly_trend": trend,
        "month_category_breakdown": current["category_breakdown"],
        "expense_change_percent": round(
            (current["expenses"] - previous["expenses"])
            / previous["expenses"]
            * 100,
            1,
        )
        if previous["expenses"]
        else None,
        "forecast": forecast,
        "budget_risks": risks,
        "unusual_spending": anomalies,
        "savings_target": saving_target,
        "savings_goals": goal_progress,
        "upcoming_bills": bills,
        "recommendations": recommendations,
    }


def llm_financial_context(analysis: dict) -> dict:
    """Select aggregate fields needed by the LLM and omit direct identifiers."""
    return {
        "currency": "UGX",
        "period": analysis["period"],
        "current_month": analysis["monthly_summary"],
        "previous_month": analysis["previous_month"],
        "monthly_trend": analysis["monthly_trend"],
        "budget_risks": analysis["budget_risks"],
        "forecast": analysis["forecast"],
        "unusual_spending": [
            {
                "category": anomaly["category"],
                "amount": anomaly["amount"],
                "usual_amount": anomaly["usual_amount"],
                "times_higher": anomaly["times_higher"],
                "date": anomaly["date"],
                "explanation": anomaly.get("explanation"),
            }
            for anomaly in analysis["unusual_spending"]
        ],
        "savings_target": analysis["savings_target"],
        "savings_goals": [
            {
                "target_amount": goal["target_amount"],
                "saved_amount": goal["saved_amount"],
                "amount_remaining": goal["amount_remaining"],
                "percent_saved": goal["percent_saved"],
                "deadline": goal["deadline"],
                "monthly_needed": goal["monthly_needed"],
                "is_completed": goal["is_completed"],
            }
            for goal in analysis["savings_goals"]
        ],
        "upcoming_bills": [
            {
                "category": bill["category"],
                "amount": bill["amount"],
                "frequency": bill["frequency"],
                "next_due_date": bill["next_due_date"],
                "is_overdue": bill["is_overdue"],
            }
            for bill in analysis["upcoming_bills"]
        ],
        "data_limitations": [
            "Forecasts are estimates based on recorded transaction history and are not guaranteed.",
            "Only recorded income and expenses are included; external accounts and unrecorded activity are not known.",
        ],
    }
