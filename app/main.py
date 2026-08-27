from fastapi import FastAPI
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
