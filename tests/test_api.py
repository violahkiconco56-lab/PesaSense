from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services.ai import AIServiceError
from app.routers import transactions as transaction_routes


SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def register_and_login(email="user@example.com", username="userone"):
    response = client.post(
        "/users/",
        json={
            "username": username,
            "email": email,
            "password": "password123",
        },
    )
    assert response.status_code == 201

    login_response = client.post(
        "/users/login",
        data={
            "username": email,
            "password": "password123",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_user_profile_update_and_password_change():
    headers = register_and_login()

    profile_response = client.get("/users/me", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == "user@example.com"

    update_response = client.put(
        "/users/me",
        headers=headers,
        json={"username": "updateduser"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["username"] == "updateduser"

    password_response = client.put(
        "/users/me/password",
        headers=headers,
        json={
            "current_password": "password123",
            "new_password": "newpassword123",
        },
    )
    assert password_response.status_code == 204


def test_transaction_filters_and_validation():
    headers = register_and_login()

    first_response = client.post(
        "/transactions/",
        headers=headers,
        json={
            "amount": 100,
            "transaction_type": "expense",
            "category": "food",
            "description": "Lunch",
            "date": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/transactions/",
        headers=headers,
        json={
            "amount": 500,
            "transaction_type": "income",
            "category": "salary",
            "date": datetime(2026, 8, 2, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert second_response.status_code == 200

    invalid_response = client.post(
        "/transactions/",
        headers=headers,
        json={
            "amount": 0,
            "transaction_type": "transfer",
            "category": "food",
        },
    )
    assert invalid_response.status_code == 422

    filter_response = client.get(
        "/transactions/?transaction_type=expense&category=Food&search=Lunch",
        headers=headers,
    )
    assert filter_response.status_code == 200
    transactions = filter_response.json()
    assert len(transactions) == 1
    assert transactions[0]["category"] == "Food"


def test_budget_duplicate_prevention_performance_and_alerts():
    headers = register_and_login()

    budget_response = client.post(
        "/budgets/",
        headers=headers,
        json={
            "category": "Food",
            "limit_amount": 100,
            "month": 8,
            "year": 2026,
        },
    )
    assert budget_response.status_code == 200

    duplicate_response = client.post(
        "/budgets/",
        headers=headers,
        json={
            "category": "food",
            "limit_amount": 200,
            "month": 8,
            "year": 2026,
        },
    )
    assert duplicate_response.status_code == 409

    transaction_response = client.post(
        "/transactions/",
        headers=headers,
        json={
            "amount": 90,
            "transaction_type": "expense",
            "category": "Food",
            "date": datetime(2026, 8, 5, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert transaction_response.status_code == 200

    performance_response = client.get(
        "/budgets/performance?month=8&year=2026",
        headers=headers,
    )
    assert performance_response.status_code == 200
    performance = performance_response.json()
    assert performance["total_spent"] == 90
    assert performance["budgets"][0]["approaching_limit"] is True

    alerts_response = client.get("/budgets/alerts", headers=headers)
    assert alerts_response.status_code == 200
    assert alerts_response.json()["alerts"][0]["type"] == "approaching_limit"


def test_reports_and_ai_fallback(monkeypatch):
    headers = register_and_login()

    response = client.post(
        "/transactions/",
        headers=headers,
        json={
            "amount": 50,
            "transaction_type": "expense",
            "category": "Transport",
            "date": datetime(2026, 8, 7, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 200

    report_response = client.get(
        "/reports/monthly?month=8&year=2026",
        headers=headers,
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["total_expenses"] == 50
    assert report["category_breakdown"]["Transport"] == 50

    monkeypatch.setattr(
        transaction_routes,
        "answer_finance_question",
        lambda question, context, history: "Test provider response.",
    )
    ai_response = client.post(
        "/transactions/insights/question",
        headers=headers,
        json={"question": "How can I reduce my spending?"},
    )
    assert ai_response.status_code == 200
    assert "answer" in ai_response.json()


def test_financial_insights_use_aggregates_and_report_ai_unavailable(monkeypatch):
    headers = register_and_login()
    now = datetime.now(timezone.utc)
    descriptions = ["Private merchant detail", "Private salary detail"]

    for amount, transaction_type, category, description in [
        (250, "expense", "Food", descriptions[0]),
        (1000, "income", "Salary", descriptions[1]),
    ]:
        response = client.post(
            "/transactions/",
            headers=headers,
            json={
                "amount": amount,
                "transaction_type": transaction_type,
                "category": category,
                "description": description,
                "date": now.isoformat(),
            },
        )
        assert response.status_code == 200

    captured = {}

    def unavailable_summary(context):
        captured["summary"] = context
        raise AIServiceError("AI insights are unavailable.")

    def stub_answer(question, context, history):
        captured["question"] = question
        captured["chat"] = context
        captured["history"] = history
        return "Test provider response."

    monkeypatch.setattr(
        transaction_routes, "generate_financial_summary", unavailable_summary
    )
    monkeypatch.setattr(transaction_routes, "answer_finance_question", stub_answer)

    summary_response = client.get(
        "/transactions/insights/summary",
        headers=headers,
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["monthly_summary"]["income"] == 1000
    assert summary["monthly_summary"]["expenses"] == 250
    assert summary["forecast"]["is_available"] is True
    assert summary["summary"] is None
    assert summary["ai_available"] is False
    assert descriptions[0] not in str(captured["summary"])
    assert descriptions[1] not in str(captured["summary"])

    chat_response = client.post(
        "/transactions/insights/question",
        headers=headers,
        json={
            "question": "How much did I spend?",
            "history": [{"role": "user", "content": "What is my cash flow?"}],
        },
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["answer"] == "Test provider response."
    assert captured["question"] == "How much did I spend?"
    assert captured["history"] == [
        {"role": "user", "content": "What is my cash flow?"}
    ]
    assert captured["chat"]["current_month"]["expenses"] == 250
    assert descriptions[0] not in str(captured["chat"])
