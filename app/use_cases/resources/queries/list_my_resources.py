from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class ListMyResourcesQuery:
    actor_id: UUID
    limit: int = 50
    offset: int = 0


class ListMyResourcesHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types

    async def handle(self, q: ListMyResourcesQuery) -> Result[list[ResourceDto]]:
        items = await self._resources.list_by_owner(
            q.actor_id, include_deleted=False, limit=q.limit, offset=q.offset,
        )
        owner = await self._users.get_by_id(q.actor_id)
        owner_slug = owner.public_slug.value if (owner and owner.public_slug) else ""

        type_ids = {r.resource_type_id for r in items}
        rt_slugs: dict = {}
        for rt_id in type_ids:
            rt = await self._resource_types.get_by_id(rt_id)
            rt_slugs[rt_id] = rt.slug.value if rt else ""

        dtos = [
            ResourceDto.from_entity(
                r, owner_slug=owner_slug,
                resource_type_slug=rt_slugs.get(r.resource_type_id, ""),
            )
            for r in items
        ]
        return Result.success(dtos)
