from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.money import Money
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class SetBasePriceCommand:
    actor_id: UUID
    resource_id: UUID
    base_price_cents: int


class SetBasePriceHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SetBasePriceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        money_r = Money.create(cmd.base_price_cents)
        if money_r.is_failure:
            return Result.failure(money_r.error, status_code=400)

        res.set_base_price(money_r.value)
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
