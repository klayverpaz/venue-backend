from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result
from app.use_cases.catalog.dtos import ResourceTypeDto


class _RepoLike(Protocol):
    async def get_by_id(self, rt_id: UUID) -> ResourceType | None: ...
    async def update(self, rt: ResourceType) -> Result[None]: ...


@dataclass(frozen=True, slots=True)
class UpdateResourceTypeCommand:
    id: UUID
    name: str | None = None
    description: str | None = None
    attribute_schema: list[dict[str, Any]] | None = None
    is_active: bool | None = None


class UpdateResourceTypeHandler:
    def __init__(self, repo: _RepoLike) -> None:
        self._repo = repo

    async def handle(self, cmd: UpdateResourceTypeCommand) -> Result[ResourceTypeDto]:
        rt = await self._repo.get_by_id(cmd.id)
        if rt is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)

        if cmd.name is not None or cmd.description is not None:
            metadata_r = rt.update_metadata(name=cmd.name, description=cmd.description)
            if metadata_r.is_failure:
                return Result.failure(metadata_r.error, status_code=400)

        if cmd.attribute_schema is not None:
            defs: list[AttributeDefinition] = []
            errors: list[str] = []
            for raw in cmd.attribute_schema:
                try:
                    dt = AttrType(raw["data_type"])
                except ValueError:
                    errors.append(f"InvalidDataType:{raw.get('data_type')!r}")
                    continue
                r = AttributeDefinition.create(
                    key=raw["key"],
                    label=raw["label"],
                    data_type=dt,
                    required=raw.get("required", False),
                    enum_values=raw.get("enum_values"),
                )
                if r.is_failure:
                    errors.append(r.error)
                else:
                    defs.append(r.value)
            if errors:
                return Result.failure("; ".join(errors), status_code=400)

            replace_r = rt.replace_attribute_schema(defs)
            if replace_r.is_failure:
                return Result.failure(replace_r.error, status_code=400)

        if cmd.is_active is not None:
            if cmd.is_active:
                rt.activate()
            else:
                rt.deactivate()

        update_r = await self._repo.update(rt)
        if update_r.is_failure:
            return Result.failure(update_r.error, status_code=update_r.status_code or 500)

        return Result.success(ResourceTypeDto.from_entity(rt))
