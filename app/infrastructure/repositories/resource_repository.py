from __future__ import annotations
from datetime import datetime, time, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.result import Result
from app.domain.shared.value_objects.attribute_key import AttributeKey
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.iana_timezone import IanaTimezone
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.short_name import ShortName
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.domain.shared.value_objects.slug import Slug
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.infrastructure.db.mappings.resource import ResourceModel


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """SQLite + aiosqlite drop tzinfo on roundtrip; assume stored values are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _time_to_str(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _str_to_time(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _serialize_schedule(ws: WeeklySchedule) -> dict:
    return {
        wd.value.lower(): [
            {"start": _time_to_str(w.start), "end": _time_to_str(w.end)}
            for w in ws.for_weekday(wd)
        ]
        for wd in Weekday
    }


def _deserialize_schedule(payload: dict) -> WeeklySchedule:
    fields: dict[str, tuple[TimeWindow, ...]] = {}
    for wd in Weekday:
        windows_payload = payload.get(wd.value.lower(), [])
        windows = tuple(
            TimeWindow(start=_str_to_time(w["start"]), end=_str_to_time(w["end"]))
            for w in windows_payload
        )
        fields[wd.value.lower()] = windows
    return WeeklySchedule(**fields)


def _serialize_pricing_rules(rules: tuple[PricingRule, ...]) -> list[dict]:
    return [
        {
            "weekdays": sorted(wd.value for wd in r.weekdays),
            "window": {"start": _time_to_str(r.window.start), "end": _time_to_str(r.window.end)},
            "price_cents": r.price.cents,
        }
        for r in rules
    ]


def _deserialize_pricing_rules(payload: list[dict]) -> list[PricingRule]:
    return [
        PricingRule(
            weekdays=frozenset(Weekday(w) for w in r["weekdays"]),
            window=TimeWindow(
                start=_str_to_time(r["window"]["start"]),
                end=_str_to_time(r["window"]["end"]),
            ),
            price=Money(cents=r["price_cents"]),
        )
        for r in payload
    ]


def _serialize_custom_attrs(attrs: tuple[CustomAttribute, ...]) -> list[dict]:
    return [
        {"key": a.key.value, "label": a.label.value, "value": a.value.value}
        for a in attrs
    ]


def _deserialize_custom_attrs(payload: list[dict]) -> list[CustomAttribute]:
    return [
        CustomAttribute(
            key=AttributeKey(value=a["key"]),
            label=ShortName(value=a["label"]),
            value=ShortDescription(value=a["value"]),
        )
        for a in payload
    ]


def _to_entity(model: ResourceModel) -> Resource:
    res = Resource(
        id=UUID(str(model.id)),
        owner_id=UUID(str(model.owner_id)),
        resource_type_id=UUID(str(model.resource_type_id)),
        slug=Slug(value=model.slug),
        name=Name(value=model.name),
        description=ShortDescription(value=model.description),
        city=Name(value=model.city),
        region=Name(value=model.region),
        timezone=IanaTimezone(value=model.timezone),
        slot_duration_minutes=SlotDuration(minutes=model.slot_duration_minutes),
        operating_hours=_deserialize_schedule(model.operating_hours),
        base_price_cents=Money(cents=model.base_price_cents),
        customer_cancellation_cutoff_hours=CancellationCutoff(hours=model.customer_cancellation_cutoff_hours),
        base_attributes=dict(model.base_attributes or {}),
        is_published=model.is_published,
        deleted_at=_ensure_utc(model.deleted_at),
        _pricing_rules=_deserialize_pricing_rules(model.pricing_rules or []),
        _custom_attributes=_deserialize_custom_attrs(model.custom_attributes or []),
    )
    res.created_at = _ensure_utc(model.created_at)
    res.updated_at = _ensure_utc(model.updated_at)
    return res


def _to_model_kwargs(res: Resource) -> dict:
    return {
        "id": str(res.id),
        "owner_id": str(res.owner_id),
        "resource_type_id": str(res.resource_type_id),
        "slug": res.slug.value,
        "name": res.name.value,
        "description": res.description.value,
        "city": res.city.value,
        "region": res.region.value,
        "timezone": res.timezone.value,
        "slot_duration_minutes": res.slot_duration_minutes.minutes,
        "base_price_cents": res.base_price_cents.cents,
        "customer_cancellation_cutoff_hours": res.customer_cancellation_cutoff_hours.hours,
        "operating_hours": _serialize_schedule(res.operating_hours),
        "pricing_rules": _serialize_pricing_rules(res.pricing_rules),
        "custom_attributes": _serialize_custom_attrs(res.custom_attributes),
        "base_attributes": dict(res.base_attributes),
        "is_published": res.is_published,
        "deleted_at": res.deleted_at,
        "created_at": res.created_at,
        "updated_at": res.updated_at,
    }


class SQLAlchemyResourceRepository(IResourceRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, resource: Resource) -> Result[None]:
        model = ResourceModel(**_to_model_kwargs(resource))
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return Result.failure("SlugAlreadyTaken", status_code=409)
        return Result.success(None)

    async def update(self, resource: Resource) -> Result[None]:
        stmt = select(ResourceModel).where(ResourceModel.id == str(resource.id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return Result.failure("ResourceNotFound", status_code=404)
        kwargs = _to_model_kwargs(resource)
        for k, v in kwargs.items():
            if k == "id":
                continue
            setattr(row, k, v)
        await self._session.flush()
        return Result.success(None)

    async def get_by_id(self, resource_id: UUID) -> Resource | None:
        stmt = select(ResourceModel).where(ResourceModel.id == str(resource_id))
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_owner_and_slug(self, owner_id: UUID, slug: str) -> Resource | None:
        stmt = select(ResourceModel).where(
            ResourceModel.owner_id == str(owner_id),
            ResourceModel.slug == slug,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_by_owner(
        self, owner_id, *, include_deleted=False, limit=50, offset=0,
    ):
        stmt = select(ResourceModel).where(ResourceModel.owner_id == str(owner_id))
        if not include_deleted:
            stmt = stmt.where(ResourceModel.deleted_at.is_(None))
        stmt = stmt.order_by(ResourceModel.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_published(
        self,
        *,
        resource_type_slug: str | None = None,
        city: str | None = None,
        region: str | None = None,
        owner_ids_filter: Iterable[UUID] | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        stmt = select(ResourceModel).where(
            ResourceModel.is_published.is_(True),
            ResourceModel.deleted_at.is_(None),
        )
        if city is not None:
            stmt = stmt.where(ResourceModel.city == city)
        if region is not None:
            stmt = stmt.where(ResourceModel.region == region)
        if owner_ids_filter is not None:
            ids_list = [str(i) for i in owner_ids_filter]
            if not ids_list:
                return []
            stmt = stmt.where(ResourceModel.owner_id.in_(ids_list))
        if resource_type_slug is not None:
            from app.infrastructure.db.mappings.resource_type import ResourceTypeModel
            stmt = stmt.join(
                ResourceTypeModel,
                ResourceTypeModel.id == ResourceModel.resource_type_id,
            ).where(ResourceTypeModel.slug == resource_type_slug)
        stmt = stmt.order_by(ResourceModel.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]

    async def list_published_by_owner(self, owner_id, *, limit=50, offset=0):
        stmt = (
            select(ResourceModel)
            .where(
                ResourceModel.owner_id == str(owner_id),
                ResourceModel.is_published.is_(True),
                ResourceModel.deleted_at.is_(None),
            )
            .order_by(ResourceModel.created_at.desc())
            .limit(limit).offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entity(r) for r in rows]
