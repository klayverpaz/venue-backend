from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.catalog.repository import IResourceTypeRepository
from app.domain.resources.custom_attribute import CustomAttribute
from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.money import Money
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday
from app.use_cases.resources.dtos import ResourceDto


@dataclass(frozen=True, slots=True)
class TimeWindowInput:
    start: str  # "HH:MM"
    end: str


@dataclass(frozen=True, slots=True)
class OperatingHoursInput:
    days: dict[Weekday, list[TimeWindowInput]]


@dataclass(frozen=True, slots=True)
class PricingRuleInput:
    weekdays: list[Weekday]
    window: TimeWindowInput
    price_cents: int


@dataclass(frozen=True, slots=True)
class CustomAttributeInput:
    key: str
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class CreateResourceCommand:
    actor_id: UUID
    resource_type_id: UUID
    slug: str
    name: str
    description: str
    city: str
    region: str
    timezone: str
    slot_duration_minutes: int
    operating_hours: OperatingHoursInput
    base_price_cents: int
    customer_cancellation_cutoff_hours: int
    base_attributes: dict[str, Any]
    pricing_rules: list[PricingRuleInput]
    custom_attributes: list[CustomAttributeInput]


def _parse_time_window(tw: TimeWindowInput, *, field_path: str) -> tuple[TimeWindow | None, FieldError | None]:
    from datetime import time
    try:
        sh, sm = tw.start.split(":")
        eh, em = tw.end.split(":")
        r = TimeWindow.create(time(int(sh), int(sm)), time(int(eh), int(em)))
    except (ValueError, AttributeError):
        return None, FieldError(code="TimeWindowInvalidType", field=field_path)
    if r.is_failure:
        return None, FieldError(code=r.error, field=field_path)
    return r.value, None


class CreateResourceHandler:
    def __init__(
        self,
        resources: IResourceRepository,
        resource_types: IResourceTypeRepository,
        users: IUserRepository,
    ) -> None:
        self._resources = resources
        self._resource_types = resource_types
        self._users = users

    async def handle(self, cmd: CreateResourceCommand) -> Result[ResourceDto]:
        # 1. Actor must be OWNER.
        user = await self._users.get_by_id(cmd.actor_id)
        if user is None or user.role is not Role.OWNER:
            return Result.failure("UserIsNotOwner", status_code=403)

        # 2. ResourceType lookup + active check.
        rt = await self._resource_types.get_by_id(cmd.resource_type_id)
        if rt is None:
            return Result.failure("ResourceTypeNotFound", status_code=404)
        if not rt.is_active:
            return Result.failure("ResourceTypeInactive", status_code=422)

        errors: list[FieldError] = []

        # 3. Build composite VOs.
        # 3a. WeeklySchedule
        days_built: dict[Weekday, list[TimeWindow]] = {}
        for wd, windows_in in cmd.operating_hours.days.items():
            built: list[TimeWindow] = []
            for idx, tw_in in enumerate(windows_in):
                tw, err = _parse_time_window(
                    tw_in, field_path=f"operating_hours.days.{wd.value.lower()}[{idx}]",
                )
                if err is not None:
                    errors.append(err)
                else:
                    built.append(tw)
            days_built[wd] = built
        ws_r = WeeklySchedule.create(
            slot_duration_minutes=cmd.slot_duration_minutes,
            days=days_built,
        )
        if ws_r.is_failure and ws_r.details is not None:
            errors.extend(
                FieldError(code=e.code, field=f"operating_hours.{e.field}")
                for e in ws_r.details
            )

        # 3b. PricingRules
        rules_built: list[PricingRule] = []
        for idx, p_in in enumerate(cmd.pricing_rules):
            tw, tw_err = _parse_time_window(
                p_in.window, field_path=f"pricing_rules[{idx}].window",
            )
            if tw_err is not None:
                errors.append(tw_err)
                continue
            money_r = Money.create(p_in.price_cents)
            if money_r.is_failure:
                errors.append(FieldError(code=money_r.error, field=f"pricing_rules[{idx}].price_cents"))
                continue
            rule_r = PricingRule.create(
                weekdays=p_in.weekdays, window=tw, price=money_r.value,
            )
            if rule_r.is_failure:
                errors.append(FieldError(code=rule_r.error, field=f"pricing_rules[{idx}]"))
                continue
            rules_built.append(rule_r.value)

        # 3c. CustomAttributes
        customs_built: list[CustomAttribute] = []
        for idx, c_in in enumerate(cmd.custom_attributes):
            ca_r = CustomAttribute.create(key=c_in.key, label=c_in.label, value=c_in.value)
            if ca_r.is_failure and ca_r.details is not None:
                errors.extend(
                    FieldError(code=e.code, field=f"custom_attributes[{idx}].{e.field}")
                    for e in ca_r.details
                )
                continue
            customs_built.append(ca_r.value)

        # 4. ResourceType.validate_attributes against base_attributes.
        attr_r = rt.validate_attributes(cmd.base_attributes)
        if attr_r.is_failure and attr_r.details is not None:
            errors.extend(
                FieldError(code=e.code, field=f"base_attributes.{e.field}")
                for e in attr_r.details
            )

        # 5. Resource.create — only callable when WeeklySchedule built successfully.
        #    Run even if attr errors exist so we collect slug/name errors in one shot.
        res_r = None
        if ws_r.is_success:
            res_r = Resource.create(
                owner_id=cmd.actor_id,
                resource_type_id=cmd.resource_type_id,
                slug=cmd.slug,
                name=cmd.name,
                description=cmd.description,
                city=cmd.city,
                region=cmd.region,
                timezone=cmd.timezone,
                slot_duration_minutes=cmd.slot_duration_minutes,
                operating_hours=ws_r.value,
                base_price_cents=cmd.base_price_cents,
                customer_cancellation_cutoff_hours=cmd.customer_cancellation_cutoff_hours,
                base_attributes=cmd.base_attributes,
                pricing_rules=rules_built,
                custom_attributes=customs_built,
                is_published=False,
            )
            if res_r.is_failure and res_r.details is not None:
                errors.extend(res_r.details)
            elif res_r.is_failure:
                errors.append(FieldError(code=res_r.error, field="resource"))

        # 6. Bail with all accumulated errors.
        if errors:
            return Result.failure_many(errors, status_code=400)

        # 7. Persist.  res_r is guaranteed non-None + success here (errors would have bailed).
        assert res_r is not None and res_r.is_success
        add_r = await self._resources.add(res_r.value)
        if add_r.is_failure:
            return Result.from_failure(add_r)

        return Result.success(
            ResourceDto.from_entity(
                res_r.value,
                owner_slug=user.public_slug.value,
                resource_type_slug=rt.slug.value,
            )
        )
