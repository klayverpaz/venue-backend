from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import Settings
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.password_hasher import IPasswordHasher
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.shared.result import Result
from app.domain.subscriptions.owner_subscription import OwnerSubscription
from app.domain.subscriptions.repository import ISubscriptionRepository
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
    def __init__(
        self,
        users: IUserRepository,
        hasher: IPasswordHasher,
        subscriptions: ISubscriptionRepository,
        config: Settings,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._subscriptions = subscriptions
        self._config = config

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
            return Result.from_failure(user_r, status_code=422)

        user = user_r.value
        await self._users.add(user)

        if user.role is Role.OWNER:
            sub_r = OwnerSubscription.create_trialing(
                owner_id=user.id,
                trial_duration_days=self._config.trial_duration_days,
                now=datetime.now(timezone.utc),
            )
            if sub_r.is_failure:
                return Result.from_failure(sub_r, status_code=500)
            add_r = await self._subscriptions.add(sub_r.value)
            if add_r.is_failure:
                return Result.from_failure(add_r, status_code=500)

        return Result.success(UserDto.from_entity(user), status_code=201)
