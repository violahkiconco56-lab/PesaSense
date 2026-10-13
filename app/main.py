from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.models.user import User
from app.models.transaction import Transaction
from app.models.budget import Budget
from app.models.goal import Goal

from app.routers import transactions
from app.routers import users
from app.routers import budget
from app.routers import reports
from app.routers import analytics
from app.routers import goal



app = FastAPI(
    title="PesaSense AI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    # A literal "*" cannot be combined with allow_credentials=True: browsers
    # reject the wildcard when credentials are allowed. List the dev frontend
    # origins explicitly instead. (Base dev already avoids CORS entirely via
    # the Vite proxy in frontend/react-app/vite.config.js.)
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://pesasense-ai-frontend.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if settings.AUTO_CREATE_TABLES:
    Base.metadata.create_all(bind=engine)
app.include_router(transactions.router)
app.include_router(users.router)
app.include_router(budget.router)
app.include_router(reports.router)
app.include_router(analytics.router)
app.include_router(goal.router)


@app.get("/")
def home():
    return {
        "message": "PesaSense AI API is running"
    }
