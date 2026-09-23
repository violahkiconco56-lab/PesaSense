from app.config import settings


AI_NOT_CONFIGURED_MESSAGE = (
    "AI insights are not configured yet. Add OPENAI_API_KEY to enable "
    "personalized financial guidance."
)

AI_PACKAGE_MISSING_MESSAGE = (
    "AI insights are unavailable because the OpenAI package is not installed."
)


def get_openai_client():
    if not settings.OPENAI_API_KEY:
        return None, AI_NOT_CONFIGURED_MESSAGE

    try:
        from openai import OpenAI
    except ImportError:
        return None, AI_PACKAGE_MISSING_MESSAGE

    return OpenAI(api_key=settings.OPENAI_API_KEY), None


def call_openai(prompt: str, max_tokens: int = 300) -> str:
    client, error_message = get_openai_client()
    if error_message:
        return error_message

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
    except Exception:
        return "AI insights are temporarily unavailable. Please try again later."

    return response.choices[0].message.content


def format_ugx(amount: float) -> str:
    return f"UGX {amount:,.0f}"


FREQUENCY_LABELS = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "one_time": "one-time",
}


def describe_income(transactions: list) -> str:
    """Summarise income, highlighting recurring earnings.

    Recurring income is converted to a monthly equivalent so the model reasons
    about steady earnings instead of a single logged amount.
    """
    incomes = [
        t for t in transactions if t.transaction_type.lower() == "income"
    ]
    if not incomes:
        return "No income recorded yet."

    monthly_multiplier = {"daily": 30, "weekly": 4.33, "monthly": 1}

    total_income = sum(t.amount for t in incomes)
    monthly_equivalent = 0.0
    lines = []
    for income in incomes:
        frequency = (getattr(income, "frequency", None) or "one_time").lower()
        monthly_equivalent += income.amount * monthly_multiplier.get(frequency, 0)
        lines.append(
            f"- {format_ugx(income.amount)} "
            f"({FREQUENCY_LABELS.get(frequency, frequency)}) "
            f"from {income.category}"
        )

    return (
        f"Total logged income: {format_ugx(total_income)}\n"
        f"Estimated monthly income (recurring earnings included): "
        f"{format_ugx(monthly_equivalent)}\n"
        "Income sources:\n" + "\n".join(lines)
    )


def generate_financial_summary(transactions: list, total_income: float, total_expenses: float) -> str:
    if not transactions:
        return "No transactions found for this period yet."

    transaction_lines = "\n".join(
        f"- {t.transaction_type} | {t.category} | {format_ugx(t.amount)} | {t.date.strftime('%Y-%m-%d')}"
        for t in transactions
    )

    income_context = describe_income(transactions)

    prompt = f"""
You are a personal finance assistant for a user in Uganda. Analyze the following transactions and give the user a short, friendly summary of their spending habits.
All money amounts are in Ugandan shillings. Always report money using UGX, never USD or $.

Total income: {format_ugx(total_income)}
Total expenses: {format_ugx(total_expenses)}

Income context (use this to judge steady vs irregular earnings):
{income_context}

Transactions:
{transaction_lines}

Give:
1. A one-paragraph summary of spending patterns, noting whether income is steady (daily/weekly/monthly) or irregular
2. One specific, actionable saving suggestion
3. One brief, cautious idea about saving toward goals or investing a surplus, only if the user has income left over after expenses
Keep it concise and encouraging, not judgmental.
"""

    return call_openai(prompt, max_tokens=400)


def answer_finance_question(question: str, transactions: list, total_income: float, total_expenses: float) -> str:
    transaction_lines = "\n".join(
        f"- {t.transaction_type} | {t.category} | {format_ugx(t.amount)} | {t.date.strftime('%Y-%m-%d')}"
        for t in transactions[-50:]
    ) or "No transactions recorded yet."

    income_context = describe_income(transactions)

    prompt = f"""
You are a personal finance assistant for a user in Uganda. Answer the user's finance question using their transaction context when relevant.
All money amounts are in Ugandan shillings. Always report money using UGX, never USD or $.

Total income: {format_ugx(total_income)}
Total expenses: {format_ugx(total_expenses)}

Income context (use this to judge steady vs irregular earnings):
{income_context}

Transactions:
{transaction_lines}

Question:
{question}

Give practical, concise guidance on spending, saving or investing that fits the user's income pattern. Do not claim certainty about investments, taxes, or legal topics.
"""

    return call_openai(prompt, max_tokens=350)
