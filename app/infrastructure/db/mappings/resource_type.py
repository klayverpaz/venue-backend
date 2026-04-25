from __future__ import annotations
from uuid import UUID
from sqlalchemy import JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class ResourceTypeModel(Base, TimestampMixin):
    __tablename__ = "resource_types"

    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attribute_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
