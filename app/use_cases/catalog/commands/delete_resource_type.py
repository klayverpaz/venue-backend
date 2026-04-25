from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID
from app.domain.shared.result import Result


class _RepoLike(Protocol):
    async def delete(self, rt_id: UUID) -> Result[None]: ...


@dataclass(frozen=True, slots=True)
class DeleteResourceTypeCommand:
    id: UUID


class DeleteResourceTypeHandler:
    def __init__(self, repo: _RepoLike) -> None:
        self._repo = repo

    async def handle(self, cmd: DeleteResourceTypeCommand) -> Result[None]:
        # TODO(plan-06): inject IResourceRepository and check whether any Resource
        # references this type. Spec §5.2: "Deletion is allowed only if no
        # Resource references the type." Resource doesn't exist yet.
        return await self._repo.delete(cmd.id)
