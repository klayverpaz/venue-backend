from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.domain.accounts.role import Role
from app.domain.accounts.user import User


@dataclass(frozen=True, slots=True)
class UserDto:
    id: UUID
    email: str
    role: Role
    full_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, u: User) -> "UserDto":
        return cls(
            id=u.id,
            email=str(u.email),
            role=u.role,
            full_name=u.full_name.value,
            phone=str(u.phone) if u.phone else None,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )


@dataclass(frozen=True, slots=True)
class TokenPairDto:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserDto
