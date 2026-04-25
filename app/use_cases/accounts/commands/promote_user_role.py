from __future__ import annotations
from dataclasses import dataclass
from uuid import UUID
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.role import Role
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import UserDto


@dataclass(frozen=True, slots=True)
class PromoteUserRoleCommand:
    user_id: UUID
    new_role: Role


class PromoteUserRoleHandler:
    """Admin-only entrypoint for changing a user's role.

    The admin-only restriction is enforced at the API layer via require_role(ADMIN).
    The handler itself accepts any new_role — including ADMIN — so admins can
    promote any user (e.g., to back-fill an admin account).
    """

    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: PromoteUserRoleCommand) -> Result[UserDto]:
        user = await self._users.get_by_id(cmd.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=404)

        user.set_role(cmd.new_role)
        await self._users.update(user)
        return Result.success(UserDto.from_entity(user))
