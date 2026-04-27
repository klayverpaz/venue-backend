from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, JSON, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime

from app.infrastructure.db.base import Base, TimestampMixin


class BookingModel(Base, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        Index(
            "idx_bookings_customer_status_created",
            "customer_id", "status", "created_at",
        ),
        Index(
            "idx_bookings_resource_status_start",
            "resource_id", "status", "slot_start_at",
        ),
        Index(
            "idx_bookings_pending_start",
            "slot_start_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("resources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    slot_end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
