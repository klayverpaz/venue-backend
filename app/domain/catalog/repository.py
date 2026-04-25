from __future__ import annotations
from typing import Protocol
from uuid import UUID
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result


class IResourceTypeRepository(Protocol):
    """Persistence port for the catalog feature."""

    async def add(self, rt: ResourceType) -> Result[None]:
        """Persist a new ResourceType. Returns SlugAlreadyTaken on conflict."""
        ...

    async def update(self, rt: ResourceType) -> Result[None]:
        """Persist changes to an existing ResourceType."""
        ...

    async def delete(self, rt_id: UUID) -> Result[None]:
        """Hard-delete the row. Returns ResourceTypeNotFound if missing."""
        ...

    async def get_by_id(self, rt_id: UUID) -> ResourceType | None:
        ...

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        ...

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        """Admin list — includes inactive rows."""
        ...

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        """Public list — only is_active=True rows."""
        ...
