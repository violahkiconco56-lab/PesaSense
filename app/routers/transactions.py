from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate


router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


@router.post("/")
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):

    new_transaction = Transaction(
        amount=transaction.amount,
        transaction_type=transaction.transaction_type,
        category=transaction.category,
        description=transaction.description,
        user_id=transaction.user_id
    )

    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    return new_transaction


@router.get("/")
def get_transactions(
    db: Session = Depends(get_db)
):
    transactions = db.query(Transaction).all()
    return transactions