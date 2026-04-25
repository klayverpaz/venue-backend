from __future__ import annotations
from dataclasses import dataclass
from app.domain.accounts.repository import IUserRepository
from app.domain.accounts.jwt_service import IJwtService
from app.domain.shared.result import Result
from app.use_cases.accounts.dtos import TokenPairDto, UserDto


@dataclass(frozen=True, slots=True)
class RefreshTokenCommand:
    refresh_token: str


class RefreshTokenHandler:
    def __init__(self, users: IUserRepository, jwt_service: IJwtService) -> None:
        self._users = users
        self._jwt = jwt_service

    async def handle(self, cmd: RefreshTokenCommand) -> Result[TokenPairDto]:
        decoded = self._jwt.decode(cmd.refresh_token)
        if decoded.is_failure:
            return Result.failure(decoded.error, status_code=401)

        claims = decoded.value
        if claims.type != "refresh":
            return Result.failure(
                "Token de acesso não pode ser usado para refresh.",
                status_code=401,
            )

        user = await self._users.get_by_id(claims.user_id)
        if user is None:
            return Result.failure("Usuário não encontrado.", status_code=401)

        if not user.is_active:
            return Result.failure(
                "Conta desativada. Faça login novamente.",
                status_code=403,
            )

        pair = self._jwt.issue_pair(user_id=user.id, role=user.role)
        return Result.success(TokenPairDto(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type=pair.token_type,
            expires_in=pair.access_expires_in_seconds,
            user=UserDto.from_entity(user),
        ))
