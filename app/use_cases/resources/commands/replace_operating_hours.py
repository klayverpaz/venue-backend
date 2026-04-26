from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.field_error import FieldError
from app.domain.shared.result import Result
from app.domain.shared.value_objects.time_window import TimeWindow
from app.use_cases.resources._common import load_owned_resource
from app.use_cases.resources.commands.create_resource import (
    OperatingHoursInput, _parse_time_window,
)


@dataclass(frozen=True, slots=True)
class ReplaceOperatingHoursCommand:
    actor_id: UUID
    resource_id: UUID
    operating_hours: OperatingHoursInput


class ReplaceOperatingHoursHandler:
    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: ReplaceOperatingHoursCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        errors: list[FieldError] = []
        days_built: dict = {}
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
            slot_duration_minutes=res.slot_duration_minutes.minutes,
            days=days_built,
        )
        if ws_r.is_failure and ws_r.details is not None:
            errors.extend(
                FieldError(code=e.code, field=f"operating_hours.{e.field}")
                for e in ws_r.details
            )
        if errors:
            return Result.failure_many(errors, status_code=400)

        repl = res.replace_operating_hours(ws_r.value)
        if repl.is_failure:
            return Result.from_failure(repl, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
