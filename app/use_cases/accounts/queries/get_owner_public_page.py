from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class GetOwnerPublicPageQuery:
    owner_slug: str


@dataclass(frozen=True, slots=True)
class OwnerPublicPageDto:
    owner_id: UUID
    owner_slug: str
    full_name: str
    resources: list[ResourceDto]


class GetOwnerPublicPageHandler:
    def __init__(
        self,
        users: IUserRepository,
        subscriptions: ISubscriptionRepository,
        resources: IResourceRepository,
        resource_types: IResourceTypeRepository,
    ) -> None:
        self._users = users
        self._subscriptions = subscriptions
        self._resources = resources
        self._resource_types = resource_types

    async def handle(self, q: GetOwnerPublicPageQuery) -> Result[OwnerPublicPageDto]:
        owner = await self._users.get_by_public_slug(q.owner_slug)
        if owner is None or owner.role is not Role.OWNER or not owner.is_active:
            return Result.failure("ResourceNotFound", status_code=404)

        sub = await self._subscriptions.get_by_owner_id(owner.id)
        if sub is None or not sub.is_operational():
            return Result.failure("ResourceNotFound", status_code=404)

        items = await self._resources.list_published_by_owner(owner.id)
        type_ids = {r.resource_type_id for r in items}
        rt_slug_by_id: dict = {}
        for rt_id in type_ids:
            rt = await self._resource_types.get_by_id(rt_id)
            rt_slug_by_id[rt_id] = rt.slug.value if rt else ""

        dtos = [
            ResourceDto.from_entity(
                r,
                owner_slug=owner.public_slug.value,
                resource_type_slug=rt_slug_by_id.get(r.resource_type_id, ""),
            )
            for r in items
        ]
        return Result.success(OwnerPublicPageDto(
            owner_id=owner.id,
            owner_slug=owner.public_slug.value,
            full_name=owner.full_name.value,
            resources=dtos,
        ))
