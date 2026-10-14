from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.config import settings
from app.models.transaction import Transaction
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


def test_financial_account_crud_is_user_scoped_and_rejects_credentials():
    owner_headers = register_and_login("account-owner@example.com", "accountowner")
    other_headers = register_and_login("account-other@example.com", "accountother")

    unauthenticated = client.get("/financial-accounts/")
    assert unauthenticated.status_code == 401

    create_response = client.post(
        "/financial-accounts/",
        headers=owner_headers,
        json={
            "name": "MTN Wallet",
            "account_type": "mtn_mobile_money",
            "currency": "ugx",
        },
    )
    assert create_response.status_code == 201
    account = create_response.json()
    assert account["name"] == "MTN Wallet"
    assert account["account_type"] == "mtn_mobile_money"
    assert account["currency"] == "UGX"
    assert "user_id" not in account
    assert "pin" not in account
    assert "password" not in account

    account_id = account["id"]
    supported_types = [
        "mtn_mobile_money",
        "airtel_money",
        "bank",
        "manual",
    ]
    for account_type in supported_types[1:]:
        response = client.post(
            "/financial-accounts/",
            headers=owner_headers,
            json={"name": f"Test {account_type}", "account_type": account_type},
        )
        assert response.status_code == 201
        assert response.json()["account_type"] == account_type

    invalid_type = client.post(
        "/financial-accounts/",
        headers=owner_headers,
        json={"name": "Unknown", "account_type": "mobile"},
    )
    assert invalid_type.status_code == 422

    credential_input = client.post(
        "/financial-accounts/",
        headers=owner_headers,
        json={
            "name": "Airtel Wallet",
            "account_type": "airtel_money",
            "pin": "not-a-real-pin",
        },
    )
    assert credential_input.status_code == 422
    credential_update = client.put(
        f"/financial-accounts/{account_id}",
        headers=owner_headers,
        json={"password": "not-a-real-password"},
    )
    assert credential_update.status_code == 422

    list_response = client.get("/financial-accounts/", headers=owner_headers)
    assert list_response.status_code == 200
    assert {
        item["account_type"] for item in list_response.json()
    } == set(supported_types)
    assert client.get("/financial-accounts/", headers=other_headers).json() == []

    forbidden_read = client.put(
        f"/financial-accounts/{account_id}",
        headers=other_headers,
        json={"name": "Stolen"},
    )
    assert forbidden_read.status_code == 404
    forbidden_delete = client.delete(
        f"/financial-accounts/{account_id}",
        headers=other_headers,
    )
    assert forbidden_delete.status_code == 404

    update_response = client.put(
        f"/financial-accounts/{account_id}",
        headers=owner_headers,
        json={"name": "Primary MTN Wallet", "currency": "kes"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Primary MTN Wallet"
    assert update_response.json()["currency"] == "KES"

    delete_response = client.delete(
        f"/financial-accounts/{account_id}",
        headers=owner_headers,
    )
    assert delete_response.status_code == 204
    remaining_accounts = client.get(
        "/financial-accounts/", headers=owner_headers
    ).json()
    assert len(remaining_accounts) == len(supported_types) - 1
    assert account_id not in {item["id"] for item in remaining_accounts}


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


def create_import_account(headers, name="Statement Wallet"):
    response = client.post(
        "/financial-accounts/",
        headers=headers,
        json={"name": name, "account_type": "manual", "currency": "UGX"},
    )
    assert response.status_code == 201
    return response.json()


def test_csv_statement_preview_import_duplicates_transfers_and_totals():
    headers = register_and_login("importer@example.com", "statementimporter")
    account = create_import_account(headers)
    csv_content = (
        "date,description,amount,transaction_type,category\n"
        "2026-10-01,Market purchase,12.34,expense,food\n"
        "2026-10-01,Market purchase,12.34,expense,food\n"
        "2026-10-02,Salary,100.12345678,income,Salary\n"
        "2026-10-03,Own account transfer,55,transfer,Transfer\n"
        "not-a-date,Private row detail,-5,expense,Food\n"
        "2026-10-05,Malformed columns,5,expense,Food,extra\n"
    ).encode("utf-8")

    preview = client.post(
        "/transactions/import/preview",
        headers=headers,
        data={"account_id": str(account["id"])},
        files={"file": ("not-a-csv-name.bin", csv_content, "application/octet-stream")},
    )
    assert preview.status_code == 200
    preview_data = preview.json()
    assert preview_data["account_id"] == account["id"]
    assert preview_data["total_rows"] == 6
    assert preview_data["importable_count"] == 3
    assert preview_data["duplicate_count"] == 0
    assert preview_data["invalid_count"] == 3
    assert preview_data["rows"][0]["amount"] == "12.34"
    assert preview_data["rows"][3]["transaction_type"] == "transfer"
    assert "Transfers are not supported" in preview_data["rows"][3]["errors"][0]

    with TestingSessionLocal() as db:
        assert db.query(Transaction).count() == 0

    imported = client.post(
        "/transactions/import",
        headers=headers,
        data={"account_id": str(account["id"])},
        files={"file": ("statement.csv", csv_content, "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json() == {
        "imported_count": 3,
        "skipped_duplicate_count": 0,
        "rejected_count": 3,
    }

    with TestingSessionLocal() as db:
        imported_transactions = (
            db.query(Transaction)
            .filter(Transaction.account_id == account["id"])
            .order_by(Transaction.id)
            .all()
        )
        assert len(imported_transactions) == 3
        assert imported_transactions[0].category == "Food"
        assert [row.transaction_type for row in imported_transactions] == [
            "expense",
            "expense",
            "income",
        ]
        assert imported_transactions[0].amount == Decimal("12.34")
        assert imported_transactions[2].amount == Decimal("100.12345678")

    duplicate_preview = client.post(
        "/transactions/import/preview",
        headers=headers,
        data={"account_id": str(account["id"])},
        files={"file": ("statement.csv", csv_content, "text/csv")},
    )
    assert duplicate_preview.status_code == 200
    assert duplicate_preview.json()["duplicate_count"] == 3
    assert duplicate_preview.json()["importable_count"] == 0

    duplicate_import = client.post(
        "/transactions/import",
        headers=headers,
        data={"account_id": str(account["id"])},
        files={"file": ("statement.csv", csv_content, "text/csv")},
    )
    assert duplicate_import.status_code == 200
    assert duplicate_import.json() == {
        "imported_count": 0,
        "skipped_duplicate_count": 3,
        "rejected_count": 3,
    }

    summary = client.get("/transactions/dashboard/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["total_expenses"] == 24.68
    assert summary.json()["total_income"] == 100.12345678

    budget = client.post(
        "/budgets/",
        headers=headers,
        json={"category": "Food", "limit_amount": 30, "month": 10, "year": 2026},
    )
    assert budget.status_code == 200
    performance = client.get(
        "/budgets/performance?month=10&year=2026", headers=headers
    )
    assert performance.status_code == 200
    assert performance.json()["budgets"][0]["spent"] == 24.68

    report = client.get(
        "/reports/monthly?month=10&year=2026", headers=headers
    )
    assert report.status_code == 200
    assert report.json()["total_expenses"] == 24.68

    deleted_account = client.delete(
        f"/financial-accounts/{account['id']}", headers=headers
    )
    assert deleted_account.status_code == 204
    with TestingSessionLocal() as db:
        retained_transactions = db.query(Transaction).all()
        assert len(retained_transactions) == 3
        assert all(transaction.account_id is None for transaction in retained_transactions)


def test_csv_import_authentication_account_ownership_and_validation(monkeypatch):
    owner_headers = register_and_login("import-owner@example.com", "importowner")
    other_headers = register_and_login("import-other@example.com", "importother")
    account = create_import_account(owner_headers, "Owner Wallet")
    valid_csv = (
        "date,description,amount,transaction_type\n"
        "2026-10-01,Valid row,50,expense\n"
    ).encode("utf-8")

    unauthenticated = client.post(
        "/transactions/import/preview",
        data={"account_id": str(account["id"])},
        files={"file": ("file.csv", valid_csv, "text/csv")},
    )
    assert unauthenticated.status_code == 401

    wrong_owner = client.post(
        "/transactions/import/preview",
        headers=other_headers,
        data={"account_id": str(account["id"])},
        files={"file": ("file.csv", valid_csv, "text/csv")},
    )
    assert wrong_owner.status_code == 404

    invalid_file = client.post(
        "/transactions/import/preview",
        headers=owner_headers,
        data={"account_id": str(account["id"])},
        files={"file": ("file.csv", b"not a statement", "text/csv")},
    )
    assert invalid_file.status_code == 422
    assert "date" in invalid_file.json()["detail"]

    original_size = settings.CSV_IMPORT_MAX_BYTES
    monkeypatch.setattr(settings, "CSV_IMPORT_MAX_BYTES", 20)
    oversized = client.post(
        "/transactions/import/preview",
        headers=owner_headers,
        data={"account_id": str(account["id"])},
        files={"file": ("file.csv", valid_csv, "text/csv")},
    )
    assert oversized.status_code == 413
    monkeypatch.setattr(settings, "CSV_IMPORT_MAX_BYTES", original_size)

    monkeypatch.setattr(settings, "CSV_IMPORT_MAX_ROWS", 1)
    too_many_rows = client.post(
        "/transactions/import/preview",
        headers=owner_headers,
        data={"account_id": str(account["id"])},
        files={
            "file": (
                "file.csv",
                (
                    "date,description,amount,transaction_type\n"
                    "2026-10-01,First,1,expense\n"
                    "2026-10-02,Second,2,income\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
    )
    assert too_many_rows.status_code == 422
    assert "maximum row count" in too_many_rows.json()["detail"]

    monkeypatch.setattr(settings, "CSV_IMPORT_MAX_ROWS", 1000)
    invalid_encoding = client.post(
        "/transactions/import/preview",
        headers=owner_headers,
        data={"account_id": str(account["id"])},
        files={"file": ("file.csv", b"\xff\xfe\x00\x00", "text/csv")},
    )
    assert invalid_encoding.status_code == 422
    assert "UTF-8" in invalid_encoding.json()["detail"]


def test_csv_import_database_failure_rolls_back_all_rows():
    headers = register_and_login("import-rollback@example.com", "importrollback")
    account = create_import_account(headers)
    csv_content = (
        "date,description,amount,transaction_type\n"
        "2026-10-01,First row,10,expense\n"
        "2026-10-02,Second row,20,income\n"
    ).encode("utf-8")

    def fail_import(mapper, connection, target):
        if target.description == "Second row":
            raise RuntimeError("Simulated persistence failure")

    event.listen(Transaction, "before_insert", fail_import)
    try:
        safe_client = TestClient(app, raise_server_exceptions=False)
        response = safe_client.post(
            "/transactions/import",
            headers=headers,
            data={"account_id": str(account["id"])},
            files={"file": ("statement.csv", csv_content, "text/csv")},
        )
    finally:
        event.remove(Transaction, "before_insert", fail_import)
    assert response.status_code == 500
    with TestingSessionLocal() as db:
        assert (
            db.query(Transaction)
            .filter(Transaction.account_id == account["id"])
            .count()
            == 0
        )
