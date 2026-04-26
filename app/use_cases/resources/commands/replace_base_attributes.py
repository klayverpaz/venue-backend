from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


@dataclass(frozen=True, slots=True)
class ReplaceBaseAttributesCommand:
    actor_id: UUID
    resource_id: UUID
    base_attributes: dict[str, Any]


class ReplaceBaseAttributesHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        resource_types: IResourceTypeRepository,
    ) -> None:
        self._resources = resources
        self._resource_types = resource_types

    async def handle(self, cmd: ReplaceBaseAttributesCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        rt = await self._resource_types.get_by_id(res.resource_type_id)
        if rt is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)

        attr_r = rt.validate_attributes(cmd.base_attributes)
        if attr_r.is_failure and attr_r.details is not None:
            return Result.failure_many(
                [
                    FieldError(code=e.code, field=f"base_attributes.{e.field}")
                    for e in attr_r.details
                ],
                status_code=400,
            )

        repl = res.replace_base_attributes(cmd.base_attributes)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
