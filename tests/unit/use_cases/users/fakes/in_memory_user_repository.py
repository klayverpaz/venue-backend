from __future__ import annotations
from typing import Sequence
from uuid import UUID
from app.domain.user.user import User
from app.domain.user.repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        return next(
            (u for u in self._by_id.values() if u.email.value == normalized),
            None,
        )

    async def list_active(
        self, *, limit: int = 50, offset: int = 0
    ) -> Sequence[User]:
        values = list(self._by_id.values())
        return values[offset: offset + limit]

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def update(self, user: User) -> None:
        self._by_id[user.id] = user

    async def remove(self, user: User) -> None:
        self._by_id.pop(user.id, None)
