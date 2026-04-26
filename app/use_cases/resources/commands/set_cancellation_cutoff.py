from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class SetCancellationCutoffCommand:
    actor_id: UUID
    resource_id: UUID
    hours: int


class SetCancellationCutoffHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SetCancellationCutoffCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        cutoff_r = CancellationCutoff.create(cmd.hours)
        if cutoff_r.is_failure:
            return Result.failure(cutoff_r.error, status_code=400)

        res.set_cancellation_cutoff(cutoff_r.value)
        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
