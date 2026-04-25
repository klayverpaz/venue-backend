from __future__ import annotations
from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.accounts.repository import IUserRepository
from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
from app.domain.shared.value_objects.email import Email
from app.domain.shared.value_objects.name import Name
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
            .limit(limit).offset(offset)
        )
        rows = await self._to_list(stmt)
        return [self._to_entity(r) for r in rows]

    async def add(self, user: User) -> None:
        self._session.add(self._to_model(user))

    async def update(self, user: User) -> None:
        row = await self._session.get(UserModel, str(user.id))
        if row is None:
            raise LookupError(f"User {user.id} not found.")
        row.email = user.email.value
        row.password_hash = user.password_hash
        row.role = user.role.value
        row.full_name = user.full_name.value
        row.phone_number = user.phone.value if user.phone else None
        row.is_active = user.is_active
        row.updated_at = user.updated_at

    @staticmethod
    def _to_model(u: User) -> UserModel:
        return UserModel(
            id=str(u.id),
            email=u.email.value,
            password_hash=u.password_hash,
            role=u.role.value,
            full_name=u.full_name.value,
            phone_number=u.phone.value if u.phone else None,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        phone_vo: BrazilianPhone | None = None
        if row.phone_number:
            phone_vo = BrazilianPhone(
                value=row.phone_number,
                is_mobile=len(row.phone_number) == 14,
            )
        return User(
            id=UUID(str(row.id)),
            email=Email(value=row.email),
            password_hash=row.password_hash,
            role=Role(row.role),
            full_name=Name(value=row.full_name),
            phone=phone_vo,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
