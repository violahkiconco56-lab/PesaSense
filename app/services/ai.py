from app.config import settings


AI_NOT_CONFIGURED_MESSAGE = (
    "AI insights are not configured yet. Add OPENAI_API_KEY to enable "
    "personalized financial guidance."
)

AI_PACKAGE_MISSING_MESSAGE = (
    "AI insights are unavailable because the OpenAI package is not installed. "
    "Install it with: pip install openai"
)

AI_UNAVAILABLE_MESSAGE = (
    "AI insights are temporarily unavailable. Please try again in a moment."
)

OPENAI_MODEL = "gpt-4o-mini"

# Raised when the AI service cannot produce a real answer. Callers must
# surface this to the client as an error response instead of treating the
# text as a genuine AI answer.
class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
# Build an OpenAI client, or raise AIServiceError explaining what is wrong.
def get_openai_client():
    if not settings.OPENAI_API_KEY:
        raise AIServiceError(AI_NOT_CONFIGURED_MESSAGE, status_code=503)

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise AIServiceError(AI_PACKAGE_MISSING_MESSAGE, status_code=503) from exc
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
        max_retries=1,
    )

# Best-effort check that the AI service can be used (key + package).
def is_ai_available() -> bool:
    if not settings.OPENAI_API_KEY:
        return False
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True
# Call OpenAI and return the assistant's reply. Raises AIServiceError on any
# failure so the API layer can respond with a real error status. It never
# returns an error string as if it were a generated answer.
def call_openai(prompt: str, max_tokens: int = 300) -> str:
    client = get_openai_client()

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
    except Exception as exc:  # network, auth, rate limit, etc.
        raise AIServiceError(AI_UNAVAILABLE_MESSAGE, status_code=503) from exc
    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        raise AIServiceError(AI_UNAVAILABLE_MESSAGE, status_code=503)

    return content.strip()


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

# Describe budget usage so the model can reason about limits. Each entry is a
# dict produced by the budget router's status builder.
def describe_budgets(budgets: list) -> str:
    if not budgets:
        return "No budgets set for this period."

    return "\n".join(
        f"- {budget['category']} ({budget['month']}/{budget['year']}): "
        f"limit {format_ugx(budget['limit_amount'])}, "
        f"spent {format_ugx(budget['spent'])}, "
        f"remaining {format_ugx(budget['remaining'])} "
        f"({budget['used_percentage']}% used)"
        for budget in budgets
    )

# Build the shared data context block sent to the model for both the summary
# and the free-form question, so both reason over the same real figures.
def _build_context(
    transactions: list,
    total_income: float,
    total_expenses: float,
    budgets: list,
) -> str:
    transaction_lines = "\n".join(
        f"- {t.date.strftime('%Y-%m-%d')} | {t.transaction_type} | "
        f"{t.category} | {format_ugx(t.amount)}"
        for t in transactions
    ) or "No transactions recorded yet."

    return (
        f"Total income: {format_ugx(total_income)}\n"
        f"Total expenses: {format_ugx(total_expenses)}\n"
        f"Net balance: {format_ugx(total_income - total_expenses)}\n\n"
        f"Income context (use this to judge steady vs irregular earnings):\n"
        f"{describe_income(transactions)}\n\n"
        f"Budget context:\n{describe_budgets(budgets)}\n\n"
        f"Transactions (most recent last):\n{transaction_lines}"
    )

def generate_financial_summary(
    transactions: list,
    total_income: float,
    total_expenses: float,
    budgets: list | None = None,
) -> str:
    if not transactions:
        return "No transactions found for this period yet."

    context = _build_context(
        transactions, total_income, total_expenses, budgets or []
    )

    prompt = f"""
You are a personal finance assistant for a user in Uganda. Analyze the following real data and give the user a short, friendly summary of their spending habits.
All money amounts are in Ugandan shillings. Always report money using UGX, never USD or $.

{context}

Give:
1. A one-paragraph summary of spending patterns, noting whether income is steady (daily/weekly/monthly) or irregular
2. One specific, actionable saving suggestion
3. One brief, cautious idea about saving toward goals or investing a surplus, only if the user has income left over after expenses
Keep it concise and encouraging, not judgmental.
"""

    return call_openai(prompt, max_tokens=400)


def answer_finance_question(
    question: str,
    transactions: list,
    total_income: float,
    total_expenses: float,
    budgets: list | None = None,
) -> str:
    context = _build_context(
        transactions, total_income, total_expenses, budgets or []
    )

    prompt = f"""
You are a personal finance assistant for a user in Uganda. Answer the user's finance question using their transaction context when relevant.
All money amounts are in Ugandan shillings. Always report money using UGX, never USD or $.

{context}

Question:
{question}

Give practical, concise guidance on spending, saving or investing that fits the user's income pattern. Do not claim certainty about investments, taxes, or legal topics.
"""

    return call_openai(prompt, max_tokens=350)
