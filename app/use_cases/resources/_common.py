from __future__ import annotations
from typing import Awaitable, Callable
from uuid import UUID

from app.domain.resources.repository import IResourceRepository
from app.domain.resources.resource import Resource
from app.domain.shared.result import Result


async def load_owned_resource(
    repo: IResourceRepository,
    *,
    resource_id: UUID,
    actor_id: UUID,
) -> Result[Resource]:
    """Load a Resource and confirm `actor_id` owns it.

    Returns ResourceNotFound (404) for: missing, owned-by-someone-else,
    or already-deleted resources. Treating the three cases identically
    avoids leaking existence to non-owners.
    """
    res = await repo.get_by_id(resource_id)
    if res is None or res.owner_id != actor_id or res.is_deleted():
        return Result.failure("ResourceNotFound", status_code=404)
    return Result.success(res)
