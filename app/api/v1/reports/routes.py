from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends

from app.api.error_handler import unwrap
from app.api.v1.reports.deps import get_active_users_by_month_handler
from app.api.v1.reports.schemas import ActiveUsersByMonthResponse
from app.use_cases.reports.queries.active_users_by_month import (
    ActiveUsersByMonthHandler, ActiveUsersByMonthQuery,
)

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("/active-users-by-month", response_model=ActiveUsersByMonthResponse)
async def active_users_by_month(
    handler: Annotated[ActiveUsersByMonthHandler, Depends(get_active_users_by_month_handler)],
) -> ActiveUsersByMonthResponse:
    dto = unwrap(await handler.handle(ActiveUsersByMonthQuery()))
    return ActiveUsersByMonthResponse.from_dto(dto)
