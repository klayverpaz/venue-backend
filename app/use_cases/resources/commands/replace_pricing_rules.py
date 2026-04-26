from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.pricing_rule import PricingRule
from app.domain.resources.repository import IResourceRepository
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.money import Money
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.commands.create_resource import (
    PricingRuleInput, _parse_time_window,
)


@dataclass(frozen=True, slots=True)
class ReplacePricingRulesCommand:
    actor_id: UUID
    resource_id: UUID
    pricing_rules: list[PricingRuleInput]


class ReplacePricingRulesHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: ReplacePricingRulesCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        errors: list[FieldError] = []
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
        if errors:
            return Result.failure_many(errors, status_code=400)

        repl = res.replace_pricing_rules(rules_built)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
