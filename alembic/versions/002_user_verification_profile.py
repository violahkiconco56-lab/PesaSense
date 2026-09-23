"""Add user verification and profile fields

Revision ID: 002_user_verification_profile
Revises: 001_initial_schema
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_user_verification_profile"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("profile_picture_url", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("email_verification_token", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_users_email_verification_token"),
        "users",
        ["email_verification_token"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_email_verification_token"), table_name="users")
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "is_verified")
    op.drop_column("users", "profile_picture_url")
