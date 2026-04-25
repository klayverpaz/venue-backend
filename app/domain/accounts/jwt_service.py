from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID
from app.domain.accounts.role import Role
from app.domain.shared.result import Result


TokenType = Literal["access", "refresh"]


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Issued by login or refresh — returned to the client."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_in_seconds: int = 0  # filled by issuer


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Decoded payload — what get_current_user receives."""
    user_id: UUID
    role: Role
    type: TokenType


class IJwtService(Protocol):
    def issue_pair(self, *, user_id: UUID, role: Role) -> TokenPair: ...
    def decode(self, token: str) -> Result[TokenClaims]:
        """Parse + verify signature + check expiry. Returns Result.failure on any of those."""
