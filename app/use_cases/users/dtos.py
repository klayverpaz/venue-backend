from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from app.domain.user.user import User


@dataclass(frozen=True, slots=True)
class UserDto:
    id: UUID
    name: str
    email: str
    phone: str
    phone_display: str
    credit_score: float
    balance: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, u: User) -> "UserDto":
        return cls(
            id=u.id,
            name=u.name,
            email=str(u.email),
            phone=str(u.phone),
            phone_display=u.phone.national,
            credit_score=u.credit_score.value,
            balance=u.balance.value,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
