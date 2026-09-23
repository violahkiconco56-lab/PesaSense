"""Add frequency column to transactions

Tracks how often income is received (one_time, daily, weekly, monthly) so the
AI guidance and reports can reason about recurring earnings.

Revision ID: 003_transaction_frequency
Revises: 002_user_verification_profile
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_transaction_frequency"
down_revision: Union[str, None] = "002_user_verification_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("frequency", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "frequency")