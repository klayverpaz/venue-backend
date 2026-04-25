from __future__ import annotations
from dataclasses import dataclass
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.password_hasher import IPasswordHasher
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import UserDto


MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str
    role: Role
    full_name: str
    phone: str | None


class RegisterUserHandler:
    def __init__(self, users: IUserRepository, hasher: IPasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    async def handle(self, cmd: RegisterUserCommand) -> Result[UserDto]:
        if not cmd.role.is_self_registerable():
            return Result.failure(
                "Não é permitido registrar contas admin via cadastro público.",
                status_code=403,
            )

        if len(cmd.password) < MIN_PASSWORD_LENGTH:
            return Result.failure(
                f"Senha precisa ter ao menos {MIN_PASSWORD_LENGTH} caracteres.",
                status_code=422,
            )

        existing = await self._users.get_by_email(cmd.email)
        if existing is not None:
            return Result.failure(
                f"Email já cadastrado: {cmd.email}",
                status_code=409,
            )

        user_r = User.create(
            email=cmd.email,
            password_hash=self._hasher.hash(cmd.password),
            role=cmd.role,
            full_name=cmd.full_name,
            phone=cmd.phone,
        )
        if user_r.is_failure:
            return Result.failure(user_r.error, status_code=422)

        user = user_r.value
        await self._users.add(user)
        return Result.success(UserDto.from_entity(user), status_code=201)
