from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    # CHAR(36) works on Postgres, SQL Server, and SQLite (tests).
    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # role is a Role enum (ADMIN/OWNER/CUSTOMER) — Text is fine; index speeds role filters.
    role: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
