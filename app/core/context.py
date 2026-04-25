from __future__ import annotations
from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")
db_session: ContextVar[Optional["AsyncSession"]] = ContextVar("db_session", default=None)
user_id: ContextVar[str] = ContextVar("user_id", default="")
