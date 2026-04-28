from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.ratings.repository import IRatingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class GetMyResourceQuery:
    actor_id: UUID
    resource_id: UUID


class GetMyResourceHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
        ratings: IRatingRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types
        self._ratings = ratings

    async def handle(self, q: GetMyResourceQuery) -> Result[ResourceDto]:
        loaded = await load_owned_resource(
            self._resources, resource_id=q.resource_id, actor_id=q.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        owner = await self._users.get_by_id(res.owner_id)
        rt = await self._resource_types.get_by_id(res.resource_type_id)
        owner_slug = owner.public_slug.value if (owner and owner.public_slug) else ""
        rt_slug = rt.slug.value if rt else ""

        aggs_r = await self._ratings.get_aggregates_for_resources([res.id])
        if aggs_r.is_failure:
            return Result.from_failure(aggs_r)
        aggs = aggs_r.value

        return Result.success(
            ResourceDto.from_entity_with_aggregate(
                res,
                aggs[res.id],
                owner_slug=owner_slug,
                resource_type_slug=rt_slug,
            )
        )
