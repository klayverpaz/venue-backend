"""resources table

Revision ID: 8b5f3e7c1d92
Revises: 3f1e2d4c5a67
Create Date: 2026-04-26 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '8b5f3e7c1d92'
down_revision: Union[str, None] = '3f1e2d4c5a67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resources',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('owner_id', sa.CHAR(length=36), nullable=False),
        sa.Column('resource_type_id', sa.CHAR(length=36), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('city', sa.Text(), nullable=False),
        sa.Column('region', sa.Text(), nullable=False),
        sa.Column('timezone', sa.Text(), nullable=False),
        sa.Column('slot_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('base_price_cents', sa.BigInteger(), nullable=False),
        sa.Column('customer_cancellation_cutoff_hours', sa.Integer(), nullable=False),
        sa.Column('operating_hours', sa.JSON(), nullable=False),
        sa.Column('pricing_rules', sa.JSON(), nullable=False),
        sa.Column('custom_attributes', sa.JSON(), nullable=False),
        sa.Column('base_attributes', sa.JSON(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_type_id'], ['resource_types.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id', 'slug', name='uq_resources_owner_slug'),
    )
    op.create_index('idx_resources_published', 'resources', ['is_published', 'deleted_at'], unique=False)
    op.create_index('idx_resources_owner', 'resources', ['owner_id'], unique=False)
    op.create_index('idx_resources_type', 'resources', ['resource_type_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_resources_type', table_name='resources')
    op.drop_index('idx_resources_owner', table_name='resources')
    op.drop_index('idx_resources_published', table_name='resources')
    op.drop_table('resources')
