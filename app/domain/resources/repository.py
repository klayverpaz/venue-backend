from __future__ import annotations
from typing import Iterable, Protocol
from uuid import UUID

from app.domain.resources.resource import Resource
from app.domain.shared.result import Result


class IResourceRepository(Protocol):
    """Persistence port for the resources feature."""

    async def add(self, resource: Resource) -> Result[None]:
        """Persist a new Resource. Returns SlugAlreadyTaken (409) on
        (owner_id, slug) conflict."""
        ...

    async def update(self, resource: Resource) -> Result[None]:
        """Persist changes. Returns ResourceNotFound (404) if missing."""
        ...

    async def get_by_id(self, resource_id: UUID) -> Resource | None:
        ...

    async def get_by_owner_and_slug(
        self, owner_id: UUID, slug: str,
    ) -> Resource | None:
        ...

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        ...

    async def list_published(
        self,
        *,
        resource_type_slug: str | None = None,
        city: str | None = None,
        region: str | None = None,
        owner_ids_filter: Iterable[UUID] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        """Excludes deleted and unpublished. Owner-operational filter is at
        HANDLER level — pass via owner_ids_filter."""
        ...

    async def list_published_by_owner(
        self,
        owner_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Resource]:
        ...
