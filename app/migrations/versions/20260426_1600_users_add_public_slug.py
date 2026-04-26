"""users add public_slug

Revision ID: 3f1e2d4c5a67
Revises: 7a4c9d6e2f81
Create Date: 2026-04-26 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '3f1e2d4c5a67'
down_revision: Union[str, None] = '7a4c9d6e2f81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('public_slug', sa.Text(), nullable=True))
    op.create_index(op.f('ix_users_public_slug'), 'users', ['public_slug'], unique=False)
    op.create_unique_constraint('uq_users_public_slug', 'users', ['public_slug'])


def downgrade() -> None:
    op.drop_constraint('uq_users_public_slug', 'users', type_='unique')
    op.drop_index(op.f('ix_users_public_slug'), table_name='users')
    op.drop_column('users', 'public_slug')
