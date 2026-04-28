from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.ratings.repository import IRatingRepository
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
    owner_rating_avg: Decimal | None = None
    owner_rating_count: int = 0


class GetOwnerPublicPageHandler:
    def __init__(
        self,
        users: IUserRepository,
        subscriptions: ISubscriptionRepository,
        resources: IResourceRepository,
        resource_types: IResourceTypeRepository,
        ratings: IRatingRepository,
    ) -> None:
        self._users = users
        self._subscriptions = subscriptions
        self._resources = resources
        self._resource_types = resource_types
        self._ratings = ratings

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

        resource_ids = [r.id for r in items]
        aggs_r = await self._ratings.get_aggregates_for_resources(resource_ids)
        if aggs_r.is_failure:
            return Result.from_failure(aggs_r)
        aggs = aggs_r.value

        dtos = [
            ResourceDto.from_entity_with_aggregate(
                r,
                aggs[r.id],
                owner_slug=owner.public_slug.value,
                resource_type_slug=rt_slug_by_id.get(r.resource_type_id, ""),
            )
            for r in items
        ]

        # Owner-level rolled-up aggregate (count-weighted average)
        total_count = sum(a.count for a in aggs.values())
        if total_count == 0:
            owner_avg: Decimal | None = None
        else:
            weighted_sum = sum(
                (a.avg_score * a.count if a.avg_score is not None else Decimal(0))
                for a in aggs.values()
            )
            owner_avg = (weighted_sum / Decimal(total_count)).quantize(Decimal("0.1"))

        return Result.success(OwnerPublicPageDto(
            owner_id=owner.id,
            owner_slug=owner.public_slug.value,
            full_name=owner.full_name.value,
            resources=dtos,
            owner_rating_avg=owner_avg,
            owner_rating_count=total_count,
        ))
