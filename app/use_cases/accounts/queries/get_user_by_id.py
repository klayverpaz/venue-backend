from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.domain.accounts.repository import IUserRepository
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import UserDto


@dataclass(frozen=True, slots=True)
class GetUserByIdQuery:
    user_id: UUID


class GetUserByIdHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, q: GetUserByIdQuery) -> Result[UserDto]:
        user = await self._users.get_by_id(q.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=404)
        return Result.success(UserDto.from_entity(user))
