"""Associate transactions with accounts and support safe statement imports.

Revision ID: 007_transaction_imports
Revises: 006_financial_accounts
Create Date: 2026-10-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_transaction_imports"
down_revision: Union[str, None] = "006_financial_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.Float(),
            type_=sa.Numeric(precision=24, scale=8),
            existing_nullable=True,
        )
        batch_op.add_column(sa.Column("account_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("import_fingerprint", sa.String(length=64), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_transactions_account_id_financial_accounts",
            "financial_accounts",
            ["account_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_transactions_account_import_fingerprint",
            ["account_id", "import_fingerprint"],
        )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint(
            "uq_transactions_account_import_fingerprint", type_="unique"
        )
        batch_op.drop_constraint(
            "fk_transactions_account_id_financial_accounts", type_="foreignkey"
        )
        batch_op.drop_column("import_fingerprint")
        batch_op.drop_column("account_id")
        batch_op.alter_column(
            "amount",
            existing_type=sa.Numeric(precision=24, scale=8),
            type_=sa.Float(),
            existing_nullable=True,
        )
