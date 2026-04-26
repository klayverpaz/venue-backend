from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Self
from uuid import UUID

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.entity import BaseEntity
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.iana_timezone import IanaTimezone
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.domain.shared.value_objects.slug import Slug


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, kw_only=True)
class Resource(BaseEntity):
    """Owner-managed rentable resource.

    Cross-rule invariants on pricing_rules (overlap / alignment / containment)
    plus custom_attributes vs base_attributes disjointness are enforced in
    create() and the relevant mutators. base_attributes type validation
    against ResourceType.attribute_schema is the HANDLER's job (cross-feature).
    """

    PRICING_RULES_OVERLAP = "PricingRulesOverlap"
    PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID = "PricingRuleNotAlignedToSlotGrid"
    PRICING_RULE_OUTSIDE_OPERATING_HOURS = "PricingRuleOutsideOperatingHours"
    DUPLICATE_CUSTOM_ATTRIBUTE_KEY = "DuplicateCustomAttributeKey"
    CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE = "CustomAttributeKeyConflictsWithBase"
    RESOURCE_ALREADY_DELETED = "ResourceAlreadyDeleted"
    DELETED_AT_NOT_TZ_AWARE = "ResourceDeletedAtNotTzAware"

    owner_id: UUID
    resource_type_id: UUID

    slug: Slug
    name: Name
    description: ShortDescription
    city: Name
    region: Name
    timezone: IanaTimezone
    slot_duration_minutes: SlotDuration
    operating_hours: WeeklySchedule
    base_price_cents: Money
    customer_cancellation_cutoff_hours: CancellationCutoff

    base_attributes: dict[str, Any] = field(default_factory=dict)

    is_published: bool = False
    deleted_at: datetime | None = None

    _pricing_rules: list[PricingRule] = field(default_factory=list, repr=False)
    _custom_attributes: list[CustomAttribute] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        owner_id: UUID,
        resource_type_id: UUID,
        slug: str,
        name: str,
        description: str,
        city: str,
        region: str,
        timezone: str,
        slot_duration_minutes: int,
        operating_hours: WeeklySchedule,
        base_price_cents: int,
        customer_cancellation_cutoff_hours: int,
        base_attributes: dict[str, Any],
        pricing_rules: list[PricingRule],
        custom_attributes: list[CustomAttribute],
        is_published: bool = False,
    ) -> Result[Self]:
        errors: list[FieldError] = []

        slug_r = Slug.create(slug)
        if slug_r.is_failure:
            errors.append(FieldError(code=slug_r.error, field="slug"))

        name_r = Name.create(name)
        if name_r.is_failure:
            errors.append(FieldError(code=name_r.error, field="name"))

        desc_r = ShortDescription.create(description)
        if desc_r.is_failure:
            errors.append(FieldError(code=desc_r.error, field="description"))

        city_r = Name.create(city)
        if city_r.is_failure:
            errors.append(FieldError(code=city_r.error, field="city"))

        region_r = Name.create(region)
        if region_r.is_failure:
            errors.append(FieldError(code=region_r.error, field="region"))

        tz_r = IanaTimezone.create(timezone)
        if tz_r.is_failure:
            errors.append(FieldError(code=tz_r.error, field="timezone"))

        slot_r = SlotDuration.create(slot_duration_minutes)
        if slot_r.is_failure:
            errors.append(FieldError(code=slot_r.error, field="slot_duration_minutes"))

        price_r = Money.create(base_price_cents)
        if price_r.is_failure:
            errors.append(FieldError(code=price_r.error, field="base_price_cents"))

        cutoff_r = CancellationCutoff.create(customer_cancellation_cutoff_hours)
        if cutoff_r.is_failure:
            errors.append(FieldError(code=cutoff_r.error, field="customer_cancellation_cutoff_hours"))

        # Cross-rule pricing checks happen AFTER scalar VO validation succeeds
        # because they need slot_r.value and operating_hours intact.
        # Implemented in Task 6.

        # Custom attributes uniqueness + disjoint-with-base
        # Implemented in Task 6.

        if errors:
            return Result.failure_many(errors)

        return Result.success(cls(
            owner_id=owner_id,
            resource_type_id=resource_type_id,
            slug=slug_r.value,
            name=name_r.value,
            description=desc_r.value,
            city=city_r.value,
            region=region_r.value,
            timezone=tz_r.value,
            slot_duration_minutes=slot_r.value,
            operating_hours=operating_hours,
            base_price_cents=price_r.value,
            customer_cancellation_cutoff_hours=cutoff_r.value,
            base_attributes=dict(base_attributes),
            is_published=is_published,
            _pricing_rules=list(pricing_rules),
            _custom_attributes=list(custom_attributes),
        ))

    @property
    def pricing_rules(self) -> tuple[PricingRule, ...]:
        return tuple(self._pricing_rules)

    @property
    def custom_attributes(self) -> tuple[CustomAttribute, ...]:
        return tuple(self._custom_attributes)
