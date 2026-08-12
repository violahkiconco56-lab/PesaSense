from app.config import settings


def generate_financial_summary(transactions: list, total_income: float, total_expenses: float) -> str:
    if not transactions:
        return "No transactions found for this period yet."

    if not settings.OPENAI_API_KEY:
        return "AI insights are not configured yet. Add OPENAI_API_KEY to enable personalized financial summaries."

    try:
        from openai import OpenAI
    except ImportError:
        return "AI insights are unavailable because the OpenAI package is not installed."

    transaction_lines = "\n".join(
        f"- {t.transaction_type} | {t.category} | {t.amount} | {t.date.strftime('%Y-%m-%d')}"
        for t in transactions
    )

    prompt = f"""
You are a personal finance assistant. Analyze the following transactions and give the user a short, friendly summary of their spending habits.

Total income: {total_income}
Total expenses: {total_expenses}

Transactions:
{transaction_lines}

Give:
1. A one-paragraph summary of spending patterns
2. One specific, actionable saving suggestion
Keep it concise and encouraging, not judgmental.
"""

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )

    return response.choices[0].message.content
