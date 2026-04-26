from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from app.domain.resources.resource import Resource


@dataclass(frozen=True, slots=True)
class TimeWindowDto:
    start: str  # "HH:MM"
    end: str


@dataclass(frozen=True, slots=True)
class WeeklyScheduleDto:
    monday: list[TimeWindowDto]
    tuesday: list[TimeWindowDto]
    wednesday: list[TimeWindowDto]
    thursday: list[TimeWindowDto]
    friday: list[TimeWindowDto]
    saturday: list[TimeWindowDto]
    sunday: list[TimeWindowDto]


@dataclass(frozen=True, slots=True)
class PricingRuleDto:
    weekdays: list[str]
    window: TimeWindowDto
    price_cents: int


@dataclass(frozen=True, slots=True)
class CustomAttributeDto:
    key: str
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ResourceDto:
    id: UUID
    owner_id: UUID
    owner_slug: str
    resource_type_id: UUID
    resource_type_slug: str
    slug: str
    name: str
    description: str
    city: str
    region: str
    timezone: str
    slot_duration_minutes: int
    operating_hours: WeeklyScheduleDto
    pricing_rules: list[PricingRuleDto]
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any]
    custom_attributes: list[CustomAttributeDto]
    is_published: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(
        cls,
        res: Resource,
        *,
        owner_slug: str,
        resource_type_slug: str,
    ) -> Self:
        def _t(t):
            return f"{t.hour:02d}:{t.minute:02d}"

        from app.domain.shared.weekday import Weekday
        sched = WeeklyScheduleDto(
            **{
                wd.value.lower(): [
                    TimeWindowDto(start=_t(w.start), end=_t(w.end))
                    for w in res.operating_hours.for_weekday(wd)
                ]
                for wd in Weekday
            }
        )
        return cls(
            id=res.id,
            owner_id=res.owner_id,
            owner_slug=owner_slug,
            resource_type_id=res.resource_type_id,
            resource_type_slug=resource_type_slug,
            slug=res.slug.value,
            name=res.name.value,
            description=res.description.value,
            city=res.city.value,
            region=res.region.value,
            timezone=res.timezone.value,
            slot_duration_minutes=res.slot_duration_minutes.minutes,
            operating_hours=sched,
            pricing_rules=[
                PricingRuleDto(
                    weekdays=sorted(w.value for w in r.weekdays),
                    window=TimeWindowDto(start=_t(r.window.start), end=_t(r.window.end)),
                    price_cents=r.price.cents,
                )
                for r in res.pricing_rules
            ],
            base_price_cents=res.base_price_cents.cents,
            customer_cancellation_cutoff_hours=res.customer_cancellation_cutoff_hours.hours,
            base_attributes=dict(res.base_attributes),
            custom_attributes=[
                CustomAttributeDto(key=a.key.value, label=a.label.value, value=a.value.value)
                for a in res.custom_attributes
            ],
            is_published=res.is_published,
            deleted_at=res.deleted_at,
            created_at=res.created_at,
            updated_at=res.updated_at,
        )
