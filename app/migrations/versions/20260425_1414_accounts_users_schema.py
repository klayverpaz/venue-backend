"""accounts_users_schema

Revision ID: 2a947408b4b7
Revises: dfdcced7f53e
Create Date: 2026-04-25 14:14:53.695034

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '2a947408b4b7'
down_revision: Union[str, None] = 'dfdcced7f53e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First batch: drop legacy columns, rename name → full_name, add the new columns
    # with a server_default so that any existing rows can be back-filled.
    with op.batch_alter_table("users") as batch:
        batch.drop_column("credit_score")
        batch.drop_column("balance")
        batch.drop_column("phone")
        batch.alter_column("name", new_column_name="full_name")
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=False, server_default=""))
        batch.add_column(sa.Column("role", sa.String(length=16), nullable=False, server_default="customer"))
        batch.add_column(sa.Column("phone_number", sa.String(length=14), nullable=True))
        batch.create_index(op.f("ix_users_role"), ["role"])

    # Second batch: drop the lingering server_default on the new NOT NULL columns
    # so future INSERTs that omit them fail loudly instead of silently picking ""
    # for password_hash or "customer" for role.
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", server_default=None)
        batch.alter_column("role", server_default=None)


def downgrade() -> None:
    # First batch: drop the new columns and rename full_name back to name; add the
    # legacy columns with server_defaults so existing rows pick a value.
    with op.batch_alter_table("users") as batch:
        batch.drop_index(op.f("ix_users_role"))
        batch.drop_column("phone_number")
        batch.drop_column("role")
        batch.drop_column("password_hash")
        batch.alter_column("full_name", new_column_name="name")
        batch.add_column(sa.Column("phone", sa.VARCHAR(length=14), nullable=False, server_default=""))
        batch.add_column(sa.Column("credit_score", sa.FLOAT(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("balance", sa.FLOAT(), nullable=False, server_default="0"))

    # Second batch: drop the lingering server_defaults so the schema matches the
    # original initial-migration shape (which had no server_defaults).
    with op.batch_alter_table("users") as batch:
        batch.alter_column("phone", server_default=None)
        batch.alter_column("credit_score", server_default=None)
        batch.alter_column("balance", server_default=None)
