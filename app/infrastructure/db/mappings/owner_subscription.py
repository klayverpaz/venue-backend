from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime
from app.infrastructure.db.base import Base, TimestampMixin


class OwnerSubscriptionModel(Base, TimestampMixin):
    __tablename__ = "owner_subscriptions"
    __table_args__ = (
        Index(
            "idx_owner_subs_status_trial_end",
            "status",
            "trial_ends_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(CHAR(36), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
