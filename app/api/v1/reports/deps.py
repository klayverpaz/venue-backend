from __future__ import annotations
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session
from app.use_cases.reports.queries.active_users_by_month import ActiveUsersByMonthHandler


def get_active_users_by_month_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActiveUsersByMonthHandler:
    return ActiveUsersByMonthHandler(session)
