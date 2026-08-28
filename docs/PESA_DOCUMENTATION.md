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


