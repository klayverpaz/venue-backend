from __future__ import annotations
from pydantic import BaseModel
from app.use_cases.reports.dtos import ActiveUsersByMonthDto


class ActiveUsersByMonthRowResponse(BaseModel):
    year: int
    month: int
    active_count: int


class ActiveUsersByMonthResponse(BaseModel):
    items: list[ActiveUsersByMonthRowResponse]

    @classmethod
    def from_dto(cls, dto: ActiveUsersByMonthDto) -> "ActiveUsersByMonthResponse":
        return cls(items=[
            ActiveUsersByMonthRowResponse(
                year=r.year, month=r.month, active_count=r.active_count,
            )
            for r in dto.items
        ])
