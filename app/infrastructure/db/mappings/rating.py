from __future__ import annotations
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, Integer

from app.infrastructure.db.base import Base, TimestampMixin


class RatingModel(Base, TimestampMixin):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint(
            "score BETWEEN 1 AND 5", name="ck_ratings_score_range",
        ),
        Index("idx_ratings_resource", "resource_id"),
        Index(
            "idx_ratings_customer_created",
            "customer_id", "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(
        CHAR(36),
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
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
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
