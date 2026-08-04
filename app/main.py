from fastapi import FastAPI
from app.database import engine, Base
from app.models.user import User
from app.models.transaction import Transaction
from app.routers import transactions
from app.routers import users


app = FastAPI(
    title="PesaSense AI",
    version="1.0.0"
)


Base.metadata.create_all(bind=engine)
app.include_router(transactions.router)
app.include_router(users.router)
@app.get("/")
def home():
    return {
        "message": "PesaSense AI API is running"
    }