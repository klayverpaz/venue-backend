from __future__ import annotations
from dataclasses import dataclass
from app.use_cases.users.dtos import UserDto
from app.domain.shared.result import Result
from app.domain.user.repository import IUserRepository


@dataclass(frozen=True, slots=True)
class GetUserByEmailQuery:
    email: str


class GetUserByEmailHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, q: GetUserByEmailQuery) -> Result[UserDto]:
        user = await self._users.get_by_email(q.email)
        if user is None:
            return Result.failure(
                f"Nenhum usuário com email '{q.email}'.",
                status_code=404,
            )
        return Result.success(UserDto.from_entity(user))
