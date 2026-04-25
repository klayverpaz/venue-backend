from __future__ import annotations
from dataclasses import dataclass
from app.use_cases.users.dtos import UserDto
from app.domain.shared.result import Result
from app.domain.user.repository import IUserRepository


@dataclass(frozen=True, slots=True)
class ListActiveUsersQuery:
    limit: int = 50
    offset: int = 0


class ListActiveUsersHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, q: ListActiveUsersQuery) -> Result[list[UserDto]]:
        users = await self._users.list_active(limit=q.limit, offset=q.offset)
        return Result.success([UserDto.from_entity(u) for u in users])
