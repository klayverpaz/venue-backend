from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime

from app.infrastructure.db.base import Base, TimestampMixin


class NotificationModel(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "idx_notifications_recipient_created",
            "recipient_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    recipient_id: Mapped[UUID] = mapped_column(CHAR(36), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
