from __future__ import annotations
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.context import db_session


@asynccontextmanager
async def ai_tool_context(session: AsyncSession):
    """Expõe AsyncSession para tools do agente via ContextVar."""
    token = db_session.set(session)
    try:
        yield
    finally:
        db_session.reset(token)
