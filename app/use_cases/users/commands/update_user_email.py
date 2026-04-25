from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.use_cases.users.dtos import UserDto
from app.domain.shared.result import Result
from app.domain.user.repository import IUserRepository


@dataclass(frozen=True, slots=True)
class UpdateUserEmailCommand:
    user_id: UUID
    new_email: str


class UpdateUserEmailHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: UpdateUserEmailCommand) -> Result[UserDto]:
        user = await self._users.get_by_id(cmd.user_id)
        if user is None:
            return Result.failure(
                f"Usuário {cmd.user_id} não encontrado.",
                status_code=404,
            )

        change_r = user.change_email(cmd.new_email)
        if change_r.is_failure:
            return Result.failure(change_r.error, status_code=422)

        await self._users.update(user)
        return Result.success(UserDto.from_entity(user))
