# PesaSense-AI Project Documentation

## 1. Project Overview

PesaSense-AI is an AI-powered personal finance management system designed to help users track, understand, and manage their finances.

The system allows users to record income and expenses, create budgets, monitor spending, generate financial reports, and receive AI-powered financial insights.

The project is currently being developed as a backend API using FastAPI. A frontend will be added later.

---

## 2. Project Objectives

The main objectives of PesaSense-AI are to:

- Track personal income and expenses.
- Help users manage their budgets.
- Monitor spending habits.
- Provide financial reports.
- Alert users when they are approaching budget limits.
- Provide AI-powered financial summaries.
- Allow users to ask questions about their finances.
- Keep users' financial information protected through authentication.

---

## 3. Technology Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- JWT Authentication
- Uvicorn

### AI

- Large Language Model (LLM) integration for financial insights and questions.

### API Documentation

- Swagger UI
- OpenAPI

---

## 4. Backend Structure

The backend is organized into different components:

```text
PesaSense-AI/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   ├── schemas/
│   ├── routers/
│   └── service/
│
├── requirements.txt
├── .env
└── docs/
    └── PROJECT_DOCUMENTATION.md
```

## 5. Relworx Mobile Money

The Premium checkout uses Relworx Mobile Money for UGX payments. Keep
`RELWORX_API_KEY` and `RELWORX_ACCOUNT_NO` in the backend `PesaSense-AI/.env`
file only; never put them in the React app's environment or source. The backend
`.gitignore` excludes `.env`.

Configure these backend environment variables and restart the API:

```dotenv
RELWORX_API_KEY=your-relworx-api-key
RELWORX_ACCOUNT_NO=your-relworx-business-account-number
PREMIUM_PRICE_UGX=5000
```

Run `alembic upgrade head` before deploying the backend. In the Relworx
business-account settings, configure the webhook URL as
`https://<public-api-host>/payments/webhook`. Relworx cannot provide a PesaSense
user JWT to that callback, so the webhook is not JWT-protected; its body is
treated only as a notification and the backend confirms every status directly
with Relworx before changing a payment or subscription.

The user-facing `POST /payments/premium` and `GET /payments/{reference}` routes
require the user's JWT. Payment statuses are:

- `pending`: the request is awaiting subscriber approval or Relworx confirmation.
- `success`: Relworx confirmed payment; Premium is active for 30 days.
- `failed`: Relworx confirmed payment failure; Premium is not activated.

To make one real minimum-value test payment, temporarily set
`PREMIUM_PRICE_UGX=500` in the backend `.env`, restart the backend, sign in,
open Pricing, and submit an MTN or Airtel number in `+256` format. Approve the
request on the phone and keep the page open while it polls; if needed, use
**Check payment status**. This charges real money and must not be run as an
automated test. After Relworx confirms success, restore
`PREMIUM_PRICE_UGX=5000` and restart the backend. The pricing page's testing
notice should remain until this real payment succeeds.
