from __future__ import annotations
from dataclasses import dataclass
from app.use_cases.users.dtos import UserDto
from app.domain.shared.result import Result
from app.domain.user.user import User
from app.domain.user.repository import IUserRepository


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    name: str
    email: str
    phone: str
    credit_score: float = 0.0
    balance: float = 0.0


class CreateUserHandler:
    def __init__(self, users: IUserRepository) -> None:
        self._users = users

    async def handle(self, cmd: CreateUserCommand) -> Result[UserDto]:
        existing = await self._users.get_by_email(cmd.email)
        if existing is not None:
            return Result.failure(
                f"Email já cadastrado: {cmd.email}",
                status_code=409,
            )

        user_r = User.create(
            name=cmd.name,
            email=cmd.email,
            phone=cmd.phone,
            credit_score=cmd.credit_score,
            balance=cmd.balance,
        )
        if user_r.is_failure:
            return Result.failure(user_r.error, status_code=422)

        user = user_r.value
        await self._users.add(user)
        return Result.success(UserDto.from_entity(user), status_code=201)
