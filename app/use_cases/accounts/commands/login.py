from __future__ import annotations
from dataclasses import dataclass
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.password_hasher import IPasswordHasher
from app.domain.accounts.jwt_service import IJwtService
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import TokenPairDto, UserDto


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str


class LoginHandler:
    def __init__(
        self,
        users: IUserRepository,
        hasher: IPasswordHasher,
        jwt_service: IJwtService,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._jwt = jwt_service

    async def handle(self, cmd: LoginCommand) -> Result[TokenPairDto]:
        # Same 401 message whether the email is unknown or the password is wrong,
        # so callers can't enumerate accounts.
        invalid = Result.failure("Email ou senha inválidos.", status_code=401)

        user = await self._users.get_by_email(cmd.email)
        if user is None:
            return invalid

        if not self._hasher.verify(cmd.password, user.password_hash):
            return invalid

        if not user.is_active:
            return Result.failure(
                "Conta desativada. Contate um administrador.", status_code=403,
            )

        # Opportunistic rehash if Argon2 params have been bumped server-side.
        if self._hasher.needs_rehash(user.password_hash):
            user.change_password_hash(self._hasher.hash(cmd.password))
            await self._users.update(user)

        pair = self._jwt.issue_pair(user_id=user.id, role=user.role)
        return Result.success(TokenPairDto(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type=pair.token_type,
            expires_in=pair.access_expires_in_seconds,
            user=UserDto.from_entity(user),
        ))
