"""bookings table

Revision ID: c7d4e8f92a1b
Revises: a603a139f10e
Create Date: 2026-04-27 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'c7d4e8f92a1b'
down_revision: Union[str, None] = 'a603a139f10e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bookings',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('resource_id', sa.CHAR(length=36), nullable=False),
        sa.Column('customer_id', sa.CHAR(length=36), nullable=False),
        sa.Column('slot_start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('slot_end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('customer_note', sa.Text(), nullable=True),
        sa.Column('total_price_cents', sa.BigInteger(), nullable=False),
        sa.Column('status_history', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='RESTRICT'),
    )
    op.create_index(
        'idx_bookings_customer_status_created', 'bookings',
        ['customer_id', 'status', 'created_at'], unique=False,
    )
    op.create_index(
        'idx_bookings_resource_status_start', 'bookings',
        ['resource_id', 'status', 'slot_start_at'], unique=False,
    )

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Partial index — Postgres only.
        op.create_index(
            'idx_bookings_pending_start', 'bookings', ['slot_start_at'],
            unique=False, postgresql_where=text("status = 'PENDING'"),
        )
        # btree_gist exclusion constraint — belt-and-suspenders against
        # advisory-lock bypass. WHERE filters to APPROVED only.
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute(
            "ALTER TABLE bookings ADD CONSTRAINT bookings_no_approved_overlap "
            "EXCLUDE USING gist ("
            "  resource_id WITH =, "
            "  tstzrange(slot_start_at, slot_end_at, '[)') WITH && "
            ") WHERE (status = 'APPROVED')"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            "ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_no_approved_overlap"
        )
        op.drop_index('idx_bookings_pending_start', table_name='bookings')
    op.drop_index('idx_bookings_resource_status_start', table_name='bookings')
    op.drop_index('idx_bookings_customer_status_created', table_name='bookings')
    op.drop_table('bookings')
