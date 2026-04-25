from __future__ import annotations
from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.catalog.attribute import AttrType, AttributeDefinition
from app.domain.catalog.resource_type import ResourceType
from app.domain.shared.result import Result
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName
from app.domain.shared.value_objects.slug import Slug
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel


def _attribute_to_dict(a: AttributeDefinition) -> dict[str, Any]:
    return {
        "key": a.key.value,
        "label": a.label.value,
        "data_type": a.data_type.value,
        "required": a.required,
        "enum_values": [v.value for v in a.enum_values] if a.enum_values else None,
    }


def _attribute_from_dict(d: dict[str, Any]) -> AttributeDefinition:
    """Trusted reconstitution from DB JSON. Bypasses VO factory validation."""
    enum_vos = (
        tuple(ShortName(value=v) for v in d["enum_values"])
        if d.get("enum_values") is not None
        else None
    )
    return AttributeDefinition(
        key=AttributeKey(value=d["key"]),
        label=ShortName(value=d["label"]),
        data_type=AttrType(d["data_type"]),
        required=d["required"],
        enum_values=enum_vos,
    )


def _to_entity(model: ResourceTypeModel) -> ResourceType:
    """Trusted reconstitution from DB row."""
    rt = ResourceType(
        # CHAR(36) column round-trips as str on SQLite, UUID on Postgres asyncpg.
        # Coerce to UUID either way; matches the user_repository pattern.
        id=UUID(str(model.id)),
        slug=Slug(value=model.slug),
        name=Name(value=model.name),
        description=ShortDescription(value=model.description),
        is_active=model.is_active,
        _attribute_schema=[_attribute_from_dict(d) for d in (model.attribute_schema or [])],
    )
    rt.created_at = model.created_at
    rt.updated_at = model.updated_at
    return rt


def _to_model_dict(rt: ResourceType) -> dict[str, Any]:
    return {
        "id": str(rt.id),
        "slug": rt.slug.value,
        "name": rt.name.value,
        "description": rt.description.value,
        "is_active": rt.is_active,
        "attribute_schema": [_attribute_to_dict(a) for a in rt.attribute_schema],
        "created_at": rt.created_at,
        "updated_at": rt.updated_at,
    }


class SQLAlchemyResourceTypeRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, rt: ResourceType) -> Result[None]:
        model = ResourceTypeModel(**_to_model_dict(rt))
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("SlugAlreadyTaken", status_code=409)
        return Result.success(None)

    async def update(self, rt: ResourceType) -> Result[None]:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.id == str(rt.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        row.slug = rt.slug.value
        row.name = rt.name.value
        row.description = rt.description.value
        row.is_active = rt.is_active
        row.attribute_schema = [_attribute_to_dict(a) for a in rt.attribute_schema]
        row.updated_at = rt.updated_at
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("SlugAlreadyTaken", status_code=409)
        return Result.success(None)

    async def delete(self, rt_id: UUID) -> Result[None]:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.id == str(rt_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        await self._session.delete(row)
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, rt_id: UUID) -> ResourceType | None:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.id == str(rt_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_slug(self, slug: str) -> ResourceType | None:
        stmt = select(ResourceTypeModel).where(ResourceTypeModel.slug == slug)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        stmt = (
            select(ResourceTypeModel)
            .order_by(ResourceTypeModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> list[ResourceType]:
        stmt = (
            select(ResourceTypeModel)
            .where(ResourceTypeModel.is_active.is_(True))
            .order_by(ResourceTypeModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]
