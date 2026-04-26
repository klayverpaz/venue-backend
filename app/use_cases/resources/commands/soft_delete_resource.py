from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.shared.result import Result
from app.use_cases.resources._common import load_owned_resource


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SoftDeleteResourceCommand:
    actor_id: UUID
    resource_id: UUID


class SoftDeleteResourceHandler:
    """Plan 06 ships the plumbing only. Plan 08 will inject IBookingRepository
    to (a) reject when an APPROVED future booking exists and (b) auto-reject
    PENDING bookings on the resource in the same transaction.
    """

    def __init__(self, resources: IResourceRepository) -> None:
        self._resources = resources

    async def handle(self, cmd: SoftDeleteResourceCommand) -> Result[None]:
        loaded = await load_owned_resource(
            self._resources, resource_id=cmd.resource_id, actor_id=cmd.actor_id,
        )
        if loaded.is_failure:
            return Result.from_failure(loaded)
        res = loaded.value

        del_r = res.soft_delete(now=_utcnow())
        if del_r.is_failure:
            return Result.from_failure(del_r, status_code=400)

        save = await self._resources.update(res)
        if save.is_failure:
            return Result.from_failure(save)
        return Result.success(None)
