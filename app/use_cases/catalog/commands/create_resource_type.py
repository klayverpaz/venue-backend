from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.use_cases.catalog.dtos import ResourceTypeDto


class _RepoLike(Protocol):
    async def add(self, rt: ResourceType) -> Result[None]: ...


@dataclass(frozen=True, slots=True)
class CreateResourceTypeCommand:
    slug: str
    name: str
    description: str
    attribute_schema: list[dict[str, Any]] = field(default_factory=list)
    is_active: bool = True


class CreateResourceTypeHandler:
    def __init__(self, repo: _RepoLike) -> None:
        self._repo = repo

    async def handle(self, cmd: CreateResourceTypeCommand) -> Result[ResourceTypeDto]:
        # Build AttributeDefinition VOs from raw dict input.
        defs: list[AttributeDefinition] = []
        errors: list[FieldError] = []
        for idx, raw in enumerate(cmd.attribute_schema):
            try:
                dt = AttrType(raw["data_type"])
            except ValueError:
                errors.append(FieldError(
                    code="InvalidDataType",
                    field=f"attribute_schema[{idx}].data_type",
                ))
                continue
            r = AttributeDefinition.create(
                key=raw["key"],
                label=raw["label"],
                data_type=dt,
                required=raw.get("required", False),
                enum_values=raw.get("enum_values"),
            )
            if r.is_failure:
                errors.append(FieldError(code=r.error, field=f"attribute_schema[{idx}]"))
            else:
                defs.append(r.value)

        if errors:
            return Result.failure_many(errors, status_code=400)

        rt_r = ResourceType.create(
            slug=cmd.slug,
            name=cmd.name,
            description=cmd.description,
            attribute_schema=defs,
            is_active=cmd.is_active,
        )
        if rt_r.is_failure:
            return Result.from_failure(rt_r, status_code=400)

        add_r = await self._repo.add(rt_r.value)
        if add_r.is_failure:
            return Result.failure(add_r.error, status_code=add_r.status_code or 409)

        return Result.success(ResourceTypeDto.from_entity(rt_r.value))
