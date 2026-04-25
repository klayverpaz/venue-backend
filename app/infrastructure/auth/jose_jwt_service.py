from __future__ import annotations
from datetime import datetime, timezone, timedelta
from uuid import UUID
from jose import jwt, JWTError, ExpiredSignatureError

from app.domain.accounts.jwt_service import (
    IJwtService, TokenPair, TokenClaims, TokenType,
)
from app.domain.accounts.role import Role
from app.domain.shared.result import Result


class JoseJwtService(IJwtService):
    def __init__(
        self,
        *,
        secret_key: str,
        algorithm: str,
        access_token_expires_seconds: int,
        refresh_token_expires_seconds: int,
    ) -> None:
        self._secret = secret_key
        self._alg = algorithm
        self._access_seconds = access_token_expires_seconds
        self._refresh_seconds = refresh_token_expires_seconds

    def issue_pair(self, *, user_id: UUID, role: Role) -> TokenPair:
        now = datetime.now(timezone.utc)
        access = self._encode(user_id=user_id, role=role, type_="access",
                              now=now, ttl_seconds=self._access_seconds)
        refresh = self._encode(user_id=user_id, role=role, type_="refresh",
                               now=now, ttl_seconds=self._refresh_seconds)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            access_expires_in_seconds=self._access_seconds,
        )

    def decode(self, token: str) -> Result[TokenClaims]:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._alg])
        except ExpiredSignatureError:
            return Result.failure("Token expirado.", status_code=401)
        except JWTError as exc:
            return Result.failure(f"Token inválido: {exc}", status_code=401)

        try:
            return Result.success(TokenClaims(
                user_id=UUID(payload["sub"]),
                role=Role(payload["role"]),
                type=payload["type"],
            ))
        except (KeyError, ValueError, TypeError) as exc:
            return Result.failure(f"Token malformado: {exc}", status_code=401)

    def _encode(
        self,
        *,
        user_id: UUID,
        role: Role,
        type_: TokenType,
        now: datetime,
        ttl_seconds: int,
    ) -> str:
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "type": type_,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._alg)
