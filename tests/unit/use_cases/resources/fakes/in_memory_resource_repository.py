from __future__ import annotations
from typing import Iterable
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.shared.result import Result


class InMemoryResourceRepository(IResourceRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, Resource] = {}

    async def add(self, resource: Resource) -> Result[None]:
        for existing in self._items.values():
            if existing.owner_id == resource.owner_id and existing.slug.value == resource.slug.value:
                return Result.failure("SlugAlreadyTaken", status_code=409)
        self._items[resource.id] = resource
        return Result.success(None)

    async def update(self, resource: Resource) -> Result[None]:
        if resource.id not in self._items:
            return Result.failure("ResourceNotFound", status_code=404)
        self._items[resource.id] = resource
        return Result.success(None)

    async def get_by_id(self, resource_id: UUID) -> Resource | None:
        return self._items.get(resource_id)

    async def get_by_owner_and_slug(self, owner_id, slug):
        for r in self._items.values():
            if r.owner_id == owner_id and r.slug.value == slug:
                return r
        return None

    async def list_by_owner(
        self, owner_id, *, include_deleted=False, limit=50, offset=0,
    ):
        items = [r for r in self._items.values() if r.owner_id == owner_id]
        if not include_deleted:
            items = [r for r in items if not r.is_deleted()]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[offset:offset + limit]

    async def list_published(
        self,
        *,
        resource_type_slug: str | None = None,
        city: str | None = None,
        region: str | None = None,
        owner_ids_filter: Iterable[UUID] | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        items = [r for r in self._items.values() if r.is_published and not r.is_deleted()]
        if city is not None:
            items = [r for r in items if r.city.value == city]
        if region is not None:
            items = [r for r in items if r.region.value == region]
        if owner_ids_filter is not None:
            allow = set(owner_ids_filter)
            items = [r for r in items if r.owner_id in allow]
        # resource_type_slug filter is handled via cross-feature lookup; the
        # handler tests for ListPublicResourcesHandler don't use this filter
        # directly. Tests that need it can extend by injecting a fake
        # ResourceTypeRepository alongside.
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[offset:offset + limit]

    async def list_published_by_owner(self, owner_id, *, limit=50, offset=0):
        items = [
            r for r in self._items.values()
            if r.owner_id == owner_id and r.is_published and not r.is_deleted()
        ]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[offset:offset + limit]
