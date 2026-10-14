
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user
from app.services.predictions import (
    forecast_month_end,
    budget_risks,
    detect_anomalies,
    savings_target,
)

router = APIRouter(
    prefix="/predictions",
    tags=["Predictions"],
)


@router.get("/forecast")
def get_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_month_end(db, current_user.id)


@router.get("/budget-risks")
def get_budget_risks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return budget_risks(db, current_user.id)


@router.get("/anomalies")
def get_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return detect_anomalies(db, current_user.id)


@router.get("/savings-target")
def get_savings_target(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return savings_target(db, current_user.id)
