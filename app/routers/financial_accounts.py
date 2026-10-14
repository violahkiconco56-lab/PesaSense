from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.financial_account import FinancialAccount
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.financial_account import (
    FinancialAccountCreate,
    FinancialAccountResponse,
    FinancialAccountUpdate,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/financial-accounts", tags=["Financial Accounts"])


def get_user_account(
    db: Session, account_id: int, user_id: int
) -> FinancialAccount:
    account = (
        db.query(FinancialAccount)
        .filter(
            FinancialAccount.id == account_id,
            FinancialAccount.user_id == user_id,
        )
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found",
        )
    return account


@router.post("/", response_model=FinancialAccountResponse, status_code=status.HTTP_201_CREATED)
def create_financial_account(
    data: FinancialAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = FinancialAccount(**data.model_dump(), user_id=current_user.id)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/", response_model=list[FinancialAccountResponse])
def list_financial_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(FinancialAccount)
        .filter(FinancialAccount.user_id == current_user.id)
        .order_by(FinancialAccount.created_at.desc(), FinancialAccount.id.desc())
        .all()
    )


@router.put("/{account_id}", response_model=FinancialAccountResponse)
def update_financial_account(
    account_id: int,
    data: FinancialAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = get_user_account(db, account_id, current_user.id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_financial_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = get_user_account(db, account_id, current_user.id)
    db.query(Transaction).filter(
        Transaction.account_id == account.id,
        Transaction.user_id == current_user.id,
    ).update({Transaction.account_id: None}, synchronize_session=False)
    db.delete(account)
    db.commit()
