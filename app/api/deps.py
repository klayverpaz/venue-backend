"""Cross-cutting API dependencies.

DI específica de feature mora em `app/api/v1/<feature>/deps.py`.
Este módulo abriga as dependências compartilhadas entre features:
identidade do usuário corrente e guards baseados em Role.
"""
from __future__ import annotations
from typing import Annotated, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.domain.accounts.jwt_service import IJwtService, TokenClaims
from app.domain.accounts.role import Role
from app.infrastructure.auth.jose_jwt_service import JoseJwtService

_bearer = HTTPBearer(auto_error=False)


def get_jwt_service() -> IJwtService:
    s = get_settings()
    return JoseJwtService(
        secret_key=s.jwt_secret_key.get_secret_value(),
        algorithm=s.jwt_algorithm,
        access_token_expires_seconds=s.jwt_access_token_expires_minutes * 60,
        refresh_token_expires_seconds=s.jwt_refresh_token_expires_days * 24 * 3600,
    )


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    jwt_service: Annotated[IJwtService, Depends(get_jwt_service)],
) -> TokenClaims:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    decoded = jwt_service.decode(creds.credentials)
    if decoded.is_failure:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=decoded.error or "Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if decoded.value.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh tokens não podem ser usados como credenciais.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decoded.value


CurrentUser = Annotated[TokenClaims, Depends(get_current_user)]


def require_role(*allowed: Role) -> Callable[[TokenClaims], TokenClaims]:
    """Returns a dependency that 403s if the current user's role isn't in `allowed`."""
    allowed_set = frozenset(allowed)

    def _dep(user: CurrentUser) -> TokenClaims:
        if user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão negada para este recurso.",
            )
        return user

    return _dep
