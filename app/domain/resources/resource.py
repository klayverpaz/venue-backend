from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.entity import BaseEntity
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff
from app.domain.shared.value_objects.date_time_range import DateTimeRange
from app.domain.shared.value_objects.iana_timezone import IanaTimezone
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.name import Name
from app.domain.shared.value_objects.short_description import ShortDescription
from app.domain.shared.value_objects.slot_duration import SlotDuration
from app.domain.shared.value_objects.slug import Slug
from app.domain.shared.weekday import Weekday


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

        # Cross-rule pricing checks (only run if scalars are sane enough to compute).
        if slot_r.is_success:
            errors.extend(cls._validate_pricing_rules(
                slot_duration_minutes=slot_r.value.minutes,
                hours=operating_hours,
                rules=pricing_rules,
            ))

        # Custom attribute uniqueness + disjoint-with-base.
        errors.extend(cls._validate_custom_attributes(
            base_attributes=base_attributes,
            customs=custom_attributes,
        ))

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

    @staticmethod
    def _validate_pricing_rules(
        *,
        slot_duration_minutes: int,
        hours: WeeklySchedule,
        rules: list[PricingRule],
    ) -> list[FieldError]:
        errors: list[FieldError] = []

        for idx, rule in enumerate(rules):
            field = f"pricing_rules[{idx}]"

            # Alignment.
            start_min = rule.window.start.hour * 60 + rule.window.start.minute
            duration = rule.window.duration_minutes()
            if (start_min % slot_duration_minutes) != 0 or (duration % slot_duration_minutes) != 0:
                errors.append(FieldError(
                    code=Resource.PRICING_RULE_NOT_ALIGNED_TO_SLOT_GRID,
                    field=field,
                ))

            # Containment: for each weekday in this rule, the rule's window must
            # fit inside at least one operating window for that weekday.
            for wd in rule.weekdays:
                day_windows = hours.for_weekday(wd)
                contained = any(
                    op.start <= rule.window.start and rule.window.end <= op.end
                    for op in day_windows
                )
                if not contained:
                    errors.append(FieldError(
                        code=Resource.PRICING_RULE_OUTSIDE_OPERATING_HOURS,
                        field=field,
                    ))
                    break  # one error per rule is enough

            # Overlap: this rule vs every previous rule on a shared weekday.
            for prev_idx in range(idx):
                prev = rules[prev_idx]
                shared = rule.weekdays & prev.weekdays
                if not shared:
                    continue
                # Time overlap: half-open intersection
                if rule.window.start < prev.window.end and prev.window.start < rule.window.end:
                    errors.append(FieldError(
                        code=Resource.PRICING_RULES_OVERLAP,
                        field=field,
                    ))
                    break

        return errors

    @staticmethod
    def _validate_custom_attributes(
        *,
        base_attributes: dict[str, Any],
        customs: list[CustomAttribute],
    ) -> list[FieldError]:
        errors: list[FieldError] = []
        seen: set[str] = set()
        base_keys = set(base_attributes.keys())

        for idx, attr in enumerate(customs):
            field = f"custom_attributes[{idx}]"
            key = attr.key.value
            if key in seen:
                errors.append(FieldError(
                    code=Resource.DUPLICATE_CUSTOM_ATTRIBUTE_KEY, field=field,
                ))
            seen.add(key)
            if key in base_keys:
                errors.append(FieldError(
                    code=Resource.CUSTOM_ATTRIBUTE_KEY_CONFLICTS_WITH_BASE, field=field,
                ))

        return errors

    def update_metadata(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        city: str | None = None,
        region: str | None = None,
    ) -> Result[None]:
        if name is None and description is None and city is None and region is None:
            return Result.success(None)

        errors: list[FieldError] = []
        new_name = self.name
        new_desc = self.description
        new_city = self.city
        new_region = self.region

        if name is not None:
            r = Name.create(name)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="name"))
            else:
                new_name = r.value

        if description is not None:
            r = ShortDescription.create(description)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="description"))
            else:
                new_desc = r.value

        if city is not None:
            r = Name.create(city)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="city"))
            else:
                new_city = r.value

        if region is not None:
            r = Name.create(region)
            if r.is_failure:
                errors.append(FieldError(code=r.error, field="region"))
            else:
                new_region = r.value

        if errors:
            return Result.failure_many(errors)

        self.name = new_name
        self.description = new_desc
        self.city = new_city
        self.region = new_region
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_operating_hours(self, hours: WeeklySchedule) -> Result[None]:
        errors = self._validate_pricing_rules(
            slot_duration_minutes=self.slot_duration_minutes.minutes,
            hours=hours,
            rules=self._pricing_rules,
        )
        if errors:
            return Result.failure_many(errors)
        self.operating_hours = hours
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_pricing_rules(self, rules: list[PricingRule]) -> Result[None]:
        errors = self._validate_pricing_rules(
            slot_duration_minutes=self.slot_duration_minutes.minutes,
            hours=self.operating_hours,
            rules=rules,
        )
        if errors:
            return Result.failure_many(errors)
        self._pricing_rules = list(rules)
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_base_attributes(self, attrs: dict[str, Any]) -> Result[None]:
        errors = self._validate_custom_attributes(
            base_attributes=attrs,
            customs=self._custom_attributes,
        )
        if errors:
            return Result.failure_many(errors)
        self.base_attributes = dict(attrs)
        self.updated_at = _utcnow()
        return Result.success(None)

    def replace_custom_attributes(self, attrs: list[CustomAttribute]) -> Result[None]:
        errors = self._validate_custom_attributes(
            base_attributes=self.base_attributes,
            customs=attrs,
        )
        if errors:
            return Result.failure_many(errors)
        self._custom_attributes = list(attrs)
        self.updated_at = _utcnow()
        return Result.success(None)

    def set_base_price(self, price: Money) -> None:
        self.base_price_cents = price
        self.updated_at = _utcnow()

    def set_cancellation_cutoff(self, cutoff: CancellationCutoff) -> None:
        self.customer_cancellation_cutoff_hours = cutoff
        self.updated_at = _utcnow()

    def set_slot_duration(self, duration: SlotDuration) -> Result[None]:
        from app.domain.shared.weekday import Weekday as _Wd
        rebuilt = WeeklySchedule.create(
            slot_duration_minutes=duration.minutes,
            days={wd: list(self.operating_hours.for_weekday(wd)) for wd in _Wd},
        )
        if rebuilt.is_failure:
            return Result.from_failure(rebuilt)

        errors = self._validate_pricing_rules(
            slot_duration_minutes=duration.minutes,
            hours=rebuilt.value,
            rules=self._pricing_rules,
        )
        if errors:
            return Result.failure_many(errors)

        self.slot_duration_minutes = duration
        self.operating_hours = rebuilt.value
        self.updated_at = _utcnow()
        return Result.success(None)

    def publish(self) -> None:
        self.is_published = True
        self.updated_at = _utcnow()

    def unpublish(self) -> None:
        self.is_published = False
        self.updated_at = _utcnow()

    def soft_delete(self, *, now: datetime) -> Result[None]:
        if now.tzinfo is None:
            return Result.failure(self.DELETED_AT_NOT_TZ_AWARE)
        if self.deleted_at is not None:
            return Result.failure(self.RESOURCE_ALREADY_DELETED)
        self.deleted_at = now
        self.updated_at = now
        return Result.success(None)

    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def compute_price(self, slot_range: DateTimeRange) -> Money:
        """Sum of per-slot prices.

        For each slot inside slot_range:
          - Convert slot_start (UTC) to the resource's timezone via astimezone.
          - Match a PricingRule when: weekday in rule.weekdays AND
            rule.window.start <= local_time_of_day < rule.window.end (half-open).
            The no-overlap invariant guarantees at most one rule matches.
          - Fall back to base_price_cents when no rule matches.
        """
        tz = ZoneInfo(self.timezone.value)
        slot_minutes = self.slot_duration_minutes.minutes
        delta = timedelta(minutes=slot_minutes)
        total = 0

        cursor = slot_range.start_at
        while cursor < slot_range.end_at:
            local = cursor.astimezone(tz)
            wd_local = Weekday.from_iso(local.isoweekday())
            tod = local.time()

            matched: PricingRule | None = None
            for rule in self._pricing_rules:
                if wd_local not in rule.weekdays:
                    continue
                if rule.window.start <= tod < rule.window.end:
                    matched = rule
                    break

            total += matched.price.cents if matched else self.base_price_cents.cents
            cursor += delta

        return Money.create(total).value
