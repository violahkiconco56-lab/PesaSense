from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import CsvUploadLimitMiddleware

from app.routers import transactions
from app.routers import users
from app.routers import budget
from app.routers import reports
from app.routers import analytics
from app.routers import goal
from app.routers import recurring_bills
from app.routers import predictions
from app.routers import financial_accounts



app = FastAPI(
    title="PesaSense AI",
    version="1.0.0"
)

app.add_middleware(
    CsvUploadLimitMiddleware,
    max_file_bytes=settings.CSV_IMPORT_MAX_BYTES,
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


app.include_router(transactions.router)
app.include_router(users.router)
app.include_router(budget.router)
app.include_router(reports.router)
app.include_router(analytics.router)
app.include_router(goal.router)
app.include_router(recurring_bills.router)
app.include_router(predictions.router)   
app.include_router(financial_accounts.router)

@app.get("/")
def home():
    return {
        "message": "PesaSense AI API is running"
    }
