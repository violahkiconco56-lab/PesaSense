"""Add user-owned financial accounts

Revision ID: 006_financial_accounts
Revises: 005_recurring_bills
Create Date: 2026-10-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_financial_accounts"
down_revision: Union[str, None] = "005_recurring_bills"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_financial_accounts_id"),
        "financial_accounts",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_accounts_user_id"),
        "financial_accounts",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_financial_accounts_user_id"), table_name="financial_accounts")
    op.drop_index(op.f("ix_financial_accounts_id"), table_name="financial_accounts")
    op.drop_table("financial_accounts")
