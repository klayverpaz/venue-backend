from __future__ import annotations
from uuid import UUID
from sqlalchemy import String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR
from app.infrastructure.db.base import Base, TimestampMixin


class UserModel(Base, TimestampMixin):
    __tablename__ = "users"

    # CHAR(36) funciona em Postgres, SQL Server e SQLite (para testes).
    # Para produção em Postgres, pode-se migrar para postgresql.UUID(as_uuid=True).
    id: Mapped[UUID] = mapped_column(CHAR(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(14), nullable=False)
    credit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
