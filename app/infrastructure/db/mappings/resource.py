from __future__ import annotations
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime

from app.infrastructure.db.base import Base, TimestampMixin


class ResourceModel(Base, TimestampMixin):
    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("owner_id", "slug", name="uq_resources_owner_slug"),
        Index("idx_resources_published", "is_published", "deleted_at"),
        Index("idx_resources_owner", "owner_id"),
        Index("idx_resources_type", "resource_type_id"),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resource_type_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("resource_types.id", ondelete="RESTRICT"),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    city: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    base_price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_cancellation_cutoff_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    operating_hours: Mapped[dict] = mapped_column(JSON, nullable=False)
    pricing_rules: Mapped[list] = mapped_column(JSON, nullable=False)
    custom_attributes: Mapped[list] = mapped_column(JSON, nullable=False)
    base_attributes: Mapped[dict] = mapped_column(JSON, nullable=False)

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
