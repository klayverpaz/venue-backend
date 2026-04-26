from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.commands.create_resource import CustomAttributeInput


@dataclass(frozen=True, slots=True)
class ReplaceCustomAttributesCommand:
    actor_id: UUID
    resource_id: UUID
    custom_attributes: list[CustomAttributeInput]


class ReplaceCustomAttributesHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: ReplaceCustomAttributesCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        errors: list[FieldError] = []
        built: list[CustomAttribute] = []
        for idx, c_in in enumerate(cmd.custom_attributes):
            ca_r = CustomAttribute.create(key=c_in.key, label=c_in.label, value=c_in.value)
            if ca_r.is_failure and ca_r.details is not None:
                errors.extend(
                    FieldError(code=e.code, field=f"custom_attributes[{idx}].{e.field}")
                    for e in ca_r.details
                )
                continue
            built.append(ca_r.value)
        if errors:
            return Result.failure_many(errors, status_code=400)

        repl = res.replace_custom_attributes(built)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
