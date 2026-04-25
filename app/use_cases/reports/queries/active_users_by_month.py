from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.result import Result
from app.use_cases.reports.dtos import ActiveUsersByMonthDto, ActiveUsersByMonthRow


@dataclass(frozen=True, slots=True)
class ActiveUsersByMonthQuery:
    pass


class ActiveUsersByMonthHandler:
    """Q anêmico: SQL direto -> DTO. Não passa por aggregate.

    Padrão para features de analytics. Ver docs/template-customization.md → Recipe D.

    NOTE: strftime é específico do SQLite. Em Postgres, troque para
    EXTRACT(YEAR FROM created_at) / EXTRACT(MONTH FROM created_at).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ActiveUsersByMonthQuery) -> Result[ActiveUsersByMonthDto]:
        rows = (await self._session.execute(text(
            """
            SELECT
                CAST(strftime('%Y', created_at) AS INTEGER) AS year,
                CAST(strftime('%m', created_at) AS INTEGER) AS month,
                COUNT(*) AS active_count
            FROM users
            WHERE is_active = 1
            GROUP BY year, month
            ORDER BY year, month
            """
        ))).all()
        items = [
            ActiveUsersByMonthRow(year=r.year, month=r.month, active_count=r.active_count)
            for r in rows
        ]
        return Result.success(ActiveUsersByMonthDto(items=items))
