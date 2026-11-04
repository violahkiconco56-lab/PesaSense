"""Add subscriptions and mobile money payments

Revision ID: 008_mobile_money_payments
Revises: 007_transaction_imports
Create Date: 2026-11-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_mobile_money_payments"
down_revision: Union[str, None] = "007_transaction_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "subscription_plan",
                sa.String(length=20),
                nullable=False,
                server_default="free",
            )
        )
        batch_op.add_column(
            sa.Column(
                "subscription_status",
                sa.String(length=20),
                nullable=False,
                server_default="active",
            )
        )
        batch_op.add_column(
            sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("msisdn", sa.String(length=16), nullable=False),
        sa.Column("reference", sa.String(length=36), nullable=False),
        sa.Column("internal_reference", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
        sa.UniqueConstraint("internal_reference"),
    )
    op.create_index(op.f("ix_payments_id"), "payments", ["id"], unique=False)
    op.create_index(
        op.f("ix_payments_status"), "payments", ["status"], unique=False
    )
    op.create_index(
        "ix_payments_user_id_created_at",
        "payments",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payments_user_id_created_at", table_name="payments")
    op.drop_index(op.f("ix_payments_status"), table_name="payments")
    op.drop_index(op.f("ix_payments_id"), table_name="payments")
    op.drop_table("payments")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("current_period_end")
        batch_op.drop_column("subscription_status")
        batch_op.drop_column("subscription_plan")
