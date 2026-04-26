from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class SetSlotDurationCommand:
    actor_id: UUID
    resource_id: UUID
    minutes: int


class SetSlotDurationHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SetSlotDurationCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        slot_r = SlotDuration.create(cmd.minutes)
        if slot_r.is_failure:
            return Result.failure(slot_r.error, status_code=400)

        upd = res.set_slot_duration(slot_r.value)
        if upd.is_failure:
            return Result.from_failure(upd, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
