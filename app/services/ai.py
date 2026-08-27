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


def generate_financial_summary(transactions: list, total_income: float, total_expenses: float) -> str:
    if not transactions:
        return "No transactions found for this period yet."

    transaction_lines = "\n".join(
        f"- {t.transaction_type} | {t.category} | {format_ugx(t.amount)} | {t.date.strftime('%Y-%m-%d')}"
        for t in transactions
    )

    prompt = f"""
You are a personal finance assistant for a user in Uganda. Analyze the following transactions and give the user a short, friendly summary of their spending habits.
All money amounts are in Ugandan shillings. Always report money using UGX, never USD or $.

Total income: {format_ugx(total_income)}
Total expenses: {format_ugx(total_expenses)}

Transactions:
{transaction_lines}

Give:
1. A one-paragraph summary of spending patterns
2. One specific, actionable saving suggestion
Keep it concise and encouraging, not judgmental.
"""

    return call_openai(prompt)

def answer_finance_question(question: str, transactions: list, total_income: float, total_expenses: float) -> str:
    transaction_lines = "\n".join(
        f"- {t.transaction_type} | {t.category} | {format_ugx(t.amount)} | {t.date.strftime('%Y-%m-%d')}"
        for t in transactions[-50:]
    ) or "No transactions recorded yet."

    prompt = f"""
You are a personal finance assistant for a user in Uganda. Answer the user's finance question using their transaction context when relevant.
All money amounts are in Ugandan shillings. Always report money using UGX, never USD or $.

Total income: {format_ugx(total_income)}
Total expenses: {format_ugx(total_expenses)}

Transactions:
{transaction_lines}

Question:
{question}

Give practical, concise guidance. Do not claim certainty about investments, taxes, or legal topics.
"""

    return call_openai(prompt, max_tokens=350)
