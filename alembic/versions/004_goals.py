"""Add goals table

Savings goals with a target amount, amount saved so far, and optional deadline.

Revision ID: 004_goals
Revises: 003_transaction_frequency
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004_goals"
down_revision: Union[str, None] = "003_transaction_frequency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("target_amount", sa.Float(), nullable=False),
        sa.Column("saved_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
    )
    op.create_index("ix_goals_id", "goals", ["id"])


def downgrade() -> None:
    op.drop_index("ix_goals_id", table_name="goals")
    op.drop_table("goals")