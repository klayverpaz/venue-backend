from __future__ import annotations
from typing import Generic, Sequence, TypeVar
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

TModel = TypeVar("TModel")


class BaseRepository(Generic[TModel]):
    def __init__(self, session: AsyncSession, model: type[TModel]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, id: UUID) -> TModel | None:
        return await self._session.get(self._model, str(id))

    def add_row(self, row: TModel) -> None:
        self._session.add(row)

    async def remove_row(self, row: TModel) -> None:
        await self._session.delete(row)

    async def _first_or_default(self, stmt: Select) -> TModel | None:
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _to_list(self, stmt: Select) -> Sequence[TModel]:
        return (await self._session.execute(stmt)).scalars().all()
