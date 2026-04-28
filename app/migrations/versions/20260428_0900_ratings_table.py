"""ratings table

Revision ID: d8a1f3c72e49
Revises: c7d4e8f92a1b
Create Date: 2026-04-28 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd8a1f3c72e49'
down_revision: Union[str, None] = 'c7d4e8f92a1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ratings',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('booking_id', sa.CHAR(length=36), nullable=False),
        sa.Column('resource_id', sa.CHAR(length=36), nullable=False),
        sa.Column('customer_id', sa.CHAR(length=36), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('booking_id', name='uq_ratings_booking'),
        sa.CheckConstraint('score BETWEEN 1 AND 5', name='ck_ratings_score_range'),
    )
    op.create_index(
        'idx_ratings_resource', 'ratings', ['resource_id'], unique=False,
    )
    op.create_index(
        'idx_ratings_customer_created', 'ratings',
        ['customer_id', 'created_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_ratings_customer_created', table_name='ratings')
    op.drop_index('idx_ratings_resource', table_name='ratings')
    op.drop_table('ratings')
