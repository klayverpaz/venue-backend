from __future__ import annotations
from dataclasses import dataclass

from app.domain.accounts.repository import IUserRepository
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.ratings.repository import IRatingRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.subscriptions.repository import ISubscriptionRepository
from app.domain.subscriptions.sub_status import SubStatus
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class ListPublicResourcesQuery:
    resource_type_slug: str | None = None
    city: str | None = None
    region: str | None = None
    limit: int = 50
    offset: int = 0


class ListPublicResourcesHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        users: IUserRepository,
        resource_types: IResourceTypeRepository,
        subscriptions: ISubscriptionRepository,
        ratings: IRatingRepository,
    ) -> None:
        self._resources = resources
        self._users = users
        self._resource_types = resource_types
        self._subscriptions = subscriptions
        self._ratings = ratings

    async def handle(self, q: ListPublicResourcesQuery) -> Result[list[ResourceDto]]:
        ops_subs = await self._subscriptions.list_all(
            status=SubStatus.ACTIVE.value, limit=10_000,
        )
        ops_subs += await self._subscriptions.list_all(
            status=SubStatus.TRIALING.value, limit=10_000,
        )
        op_owner_ids = [s.owner_id for s in ops_subs]
        owners = await self._users.list_by_ids(op_owner_ids)
        owner_active_by_id = {u.id: u for u in owners if u.is_active}
        operational_ids = list(owner_active_by_id.keys())
        if not operational_ids:
            return Result.success([])

        items = await self._resources.list_published(
            resource_type_slug=q.resource_type_slug,
            city=q.city,
            region=q.region,
            owner_ids_filter=operational_ids,
            limit=q.limit,
            offset=q.offset,
        )

        type_ids = {r.resource_type_id for r in items}
        type_slug_by_id: dict = {}
        for rt_id in type_ids:
            rt = await self._resource_types.get_by_id(rt_id)
            type_slug_by_id[rt_id] = rt.slug.value if rt else ""

        visible_items = [r for r in items if r.owner_id in owner_active_by_id]
        resource_ids = [r.id for r in visible_items]
        aggs_r = await self._ratings.get_aggregates_for_resources(resource_ids)
        if aggs_r.is_failure:
            return Result.from_failure(aggs_r)
        aggs = aggs_r.value

        dtos = [
            ResourceDto.from_entity_with_aggregate(
                r,
                aggs[r.id],
                owner_slug=owner_active_by_id[r.owner_id].public_slug.value,
                resource_type_slug=type_slug_by_id.get(r.resource_type_id, ""),
            )
            for r in visible_items
        ]
        return Result.success(dtos)
