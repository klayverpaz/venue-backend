"""owner subscriptions table

Revision ID: 7a4c9d6e2f81
Revises: 2b8ca93d5b89
Create Date: 2026-04-26 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '7a4c9d6e2f81'
down_revision: Union[str, None] = '2b8ca93d5b89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'owner_subscriptions',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('owner_id', sa.CHAR(length=36), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('status_changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_owner_subscriptions_owner_id'),
        'owner_subscriptions',
        ['owner_id'],
        unique=True,
    )
    op.create_index(
        'idx_owner_subs_status_trial_end',
        'owner_subscriptions',
        ['status', 'trial_ends_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_owner_subs_status_trial_end', table_name='owner_subscriptions')
    op.drop_index(op.f('ix_owner_subscriptions_owner_id'), table_name='owner_subscriptions')
    op.drop_table('owner_subscriptions')
