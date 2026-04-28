from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.use_cases.resources.dtos import (
    CustomAttributeDto, PricingRuleDto, ResourceDto, TimeWindowDto, WeeklyScheduleDto,
)


class TimeWindowSchema(BaseModel):
    start: str
    end: str


class WeeklyScheduleSchema(BaseModel):
    monday: list[TimeWindowSchema] = []
    tuesday: list[TimeWindowSchema] = []
    wednesday: list[TimeWindowSchema] = []
    thursday: list[TimeWindowSchema] = []
    friday: list[TimeWindowSchema] = []
    saturday: list[TimeWindowSchema] = []
    sunday: list[TimeWindowSchema] = []


class PricingRuleSchema(BaseModel):
    weekdays: list[str]
    window: TimeWindowSchema
    price_cents: int


class CustomAttributeSchema(BaseModel):
    key: str
    label: str
    value: str


class ResourceResponse(BaseModel):
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
    operating_hours: WeeklyScheduleSchema
    pricing_rules: list[PricingRuleSchema]
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any]
    custom_attributes: list[CustomAttributeSchema]
    is_published: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    rating_avg: Decimal | None = None
    rating_count: int = 0

    @classmethod
    def from_dto(cls, dto: ResourceDto) -> "ResourceResponse":
        def _tw(w: TimeWindowDto) -> TimeWindowSchema:
            return TimeWindowSchema(start=w.start, end=w.end)

        return cls(
            id=dto.id,
            owner_id=dto.owner_id,
            owner_slug=dto.owner_slug,
            resource_type_id=dto.resource_type_id,
            resource_type_slug=dto.resource_type_slug,
            slug=dto.slug,
            name=dto.name,
            description=dto.description,
            city=dto.city,
            region=dto.region,
            timezone=dto.timezone,
            slot_duration_minutes=dto.slot_duration_minutes,
            operating_hours=WeeklyScheduleSchema(**{
                "monday": [_tw(w) for w in dto.operating_hours.monday],
                "tuesday": [_tw(w) for w in dto.operating_hours.tuesday],
                "wednesday": [_tw(w) for w in dto.operating_hours.wednesday],
                "thursday": [_tw(w) for w in dto.operating_hours.thursday],
                "friday": [_tw(w) for w in dto.operating_hours.friday],
                "saturday": [_tw(w) for w in dto.operating_hours.saturday],
                "sunday": [_tw(w) for w in dto.operating_hours.sunday],
            }),
            pricing_rules=[
                PricingRuleSchema(
                    weekdays=p.weekdays,
                    window=TimeWindowSchema(start=p.window.start, end=p.window.end),
                    price_cents=p.price_cents,
                ) for p in dto.pricing_rules
            ],
            base_price_cents=dto.base_price_cents,
            customer_cancellation_cutoff_hours=dto.customer_cancellation_cutoff_hours,
            base_attributes=dto.base_attributes,
            custom_attributes=[
                CustomAttributeSchema(key=c.key, label=c.label, value=c.value)
                for c in dto.custom_attributes
            ],
            is_published=dto.is_published,
            deleted_at=dto.deleted_at,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            rating_avg=dto.rating_avg,
            rating_count=dto.rating_count,
        )


class ResourceListResponse(BaseModel):
    items: list[ResourceResponse]
    limit: int
    offset: int


class CreateResourceBody(BaseModel):
    resource_type_id: UUID
    slug: str
    name: str
    description: str = ""
    city: str
    region: str
    timezone: str
    slot_duration_minutes: int
    operating_hours: WeeklyScheduleSchema
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any] = Field(default_factory=dict)
    pricing_rules: list[PricingRuleSchema] = Field(default_factory=list)
    custom_attributes: list[CustomAttributeSchema] = Field(default_factory=list)


class UpdateResourceBody(BaseModel):
    name: str | None = None
    description: str | None = None
    city: str | None = None
    region: str | None = None
    base_price_cents: int | None = None
    customer_cancellation_cutoff_hours: int | None = None
    base_attributes: dict[str, Any] | None = None
    custom_attributes: list[CustomAttributeSchema] | None = None


class ReplaceOperatingHoursBody(BaseModel):
    operating_hours: WeeklyScheduleSchema


class ReplacePricingRulesBody(BaseModel):
    pricing_rules: list[PricingRuleSchema]


class SetSlotDurationBody(BaseModel):
    minutes: int
