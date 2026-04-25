from __future__ import annotations
from uuid import UUID
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result


class InMemoryResourceTypeRepository:
    """Test fake implementing IResourceTypeRepository."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, ResourceType] = {}

    async def add(self, rt: ResourceType) -> Result[None]:
        if any(existing.slug.value == rt.slug.value for existing in self._by_id.values()):
            return Result.failure("SlugAlreadyTaken", status_code=409)
        self._by_id[rt.id] = rt
        return Result.success(None)

    async def update(self, rt: ResourceType) -> Result[None]:
        if rt.id not in self._by_id:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        clash = next(
            (other for other in self._by_id.values()
             if other.id != rt.id and other.slug.value == rt.slug.value),
            None,
        )
        if clash is not None:
            return Result.failure("SlugAlreadyTaken", status_code=409)
        self._by_id[rt.id] = rt
        return Result.success(None)

    async def delete(self, rt_id: UUID) -> Result[None]:
        if rt_id not in self._by_id:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        del self._by_id[rt_id]
        return Result.success(None)

    async def get_by_id(self, rt_id: UUID) -> ResourceType | None:
        return self._by_id.get(rt_id)

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        return next(
            (rt for rt in self._by_id.values() if rt.slug.value == slug),
            None,
        )

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        rows = sorted(self._by_id.values(), key=lambda rt: rt.created_at)
        return rows[offset:offset + limit]

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        rows = sorted(
            (rt for rt in self._by_id.values() if rt.is_active),
            key=lambda rt: rt.created_at,
        )
        return rows[offset:offset + limit]
