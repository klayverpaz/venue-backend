"""notifications table

Revision ID: a603a139f10e
Revises: 8b5f3e7c1d92
Create Date: 2026-04-26 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a603a139f10e'
down_revision: Union[str, None] = '8b5f3e7c1d92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('recipient_id', sa.CHAR(length=36), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_notifications_recipient_created', 'notifications', ['recipient_id', 'created_at', 'id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_notifications_recipient_created', table_name='notifications')
    op.drop_table('notifications')
