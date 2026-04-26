from __future__ import annotations
from dataclasses import dataclass

from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class GetPublicResourceQuery:
    owner_slug: str
    resource_slug: str


class GetPublicResourceHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
        subscriptions: ISubscriptionRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types
        self._subscriptions = subscriptions

    async def handle(self, q: GetPublicResourceQuery) -> Result[ResourceDto]:
        owner = await self._users.get_by_public_slug(q.owner_slug)
        if owner is None or owner.role is not Role.OWNER or not owner.is_active:
            return Result.failure("ResourceNotFound", status_code=404)

        sub = await self._subscriptions.get_by_owner_id(owner.id)
        if sub is None or not sub.is_operational():
            return Result.failure("ResourceNotFound", status_code=404)

        res = await self._resources.get_by_owner_and_slug(owner.id, q.resource_slug)
        if res is None or not res.is_published or res.is_deleted():
            return Result.failure("ResourceNotFound", status_code=404)

        rt = await self._resource_types.get_by_id(res.resource_type_id)
        rt_slug = rt.slug.value if rt else ""
        return Result.success(
            ResourceDto.from_entity(
                res,
                owner_slug=owner.public_slug.value,
                resource_type_slug=rt_slug,
            )
        )
