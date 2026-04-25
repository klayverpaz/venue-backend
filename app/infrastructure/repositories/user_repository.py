from __future__ import annotations
from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.user.user import User
from app.domain.user.repository import IUserRepository
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.non_negative_float import NonNegativeFloat
from app.domain.shared.value_objects.percentage import Percentage
from app.infrastructure.db.mappings.user import UserModel
from app.infrastructure.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[UserModel], IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel)

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await super().get_by_id(user_id)
        return self._to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        stmt = select(UserModel).where(UserModel.email == normalized)
        row = await self._first_or_default(stmt)
        return self._to_entity(row) if row else None

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> Sequence[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.is_active.is_(True))
            .order_by(UserModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._to_list(stmt)
        return [self._to_entity(r) for r in rows]

    async def add(self, user: User) -> None:
        self._session.add(self._to_model(user))

    async def update(self, user: User) -> None:
        row = await self._session.get(UserModel, str(user.id))
        if row is None:
            raise LookupError(f"User {user.id} not found.")
        row.name = user.name
        row.email = user.email.value
        row.phone = user.phone.value
        row.credit_score = user.credit_score.value
        row.balance = user.balance.value
        row.updated_at = user.updated_at

    async def remove(self, user: User) -> None:
        row = await self._session.get(UserModel, str(user.id))
        if row is not None:
            await self._session.delete(row)

    @staticmethod
    def _to_model(u: User) -> UserModel:
        return UserModel(
            id=str(u.id),
            name=u.name,
            email=u.email.value,
            phone=u.phone.value,
            credit_score=u.credit_score.value,
            balance=u.balance.value,
            is_active=True,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        from uuid import UUID as _UUID
        return User(
            id=_UUID(str(row.id)),
            name=row.name,
            email=Email(value=row.email),
            phone=BrazilianPhone(value=row.phone, is_mobile=len(row.phone) == 14),
            credit_score=Percentage(value=row.credit_score),
            balance=NonNegativeFloat(value=row.balance),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
