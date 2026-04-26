from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class UpdateResourceMetadataCommand:
    actor_id: UUID
    resource_id: UUID
    name: str | None
    description: str | None
    city: str | None
    region: str | None


class UpdateResourceMetadataHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: UpdateResourceMetadataCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        upd = res.update_metadata(
            name=cmd.name, description=cmd.description,
            city=cmd.city, region=cmd.region,
        )
        if upd.is_failure:
            return Result.from_failure(upd, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
