from __future__ import annotations
from typing import Sequence
from uuid import UUID
from app.domain.accounts.user import User
from app.domain.accounts.repository import IUserRepository


class InMemoryUserRepository(IUserRepository):
    def __init__(self, *, seed: Sequence[User] = ()) -> None:
        self._by_id: dict[UUID, User] = {u.id: u for u in seed}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        target = email.strip().lower()
        for u in self._by_id.values():
            if str(u.email) == target:
                return u
        return None

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> Sequence[User]:
        active = [u for u in self._by_id.values() if u.is_active]
        active.sort(key=lambda u: u.created_at, reverse=True)
        return active[offset:offset + limit]

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def update(self, user: User) -> None:
        if user.id not in self._by_id:
            raise LookupError(f"User {user.id} not found.")
        self._by_id[user.id] = user
