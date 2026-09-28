from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.models.user import User
from app.models.transaction import Transaction
from app.models.budget import Budget

from app.routers import transactions
from app.routers import users
from app.routers import budget
from app.routers import reports


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


@app.get("/")
def home():
    return {
        "message": "PesaSense AI API is running"
    }
