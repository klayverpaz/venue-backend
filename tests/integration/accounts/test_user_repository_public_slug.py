from __future__ import annotations
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.infrastructure.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_unique_public_slug_allows_multiple_nulls(db_session: AsyncSession):
    repo = UserRepository(db_session)
    # Two CUSTOMERs both with public_slug=None should coexist.
    a = User.create(
        email="a@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="A B", phone=None, public_slug=None,
    ).value
    b = User.create(
        email="b@example.com", password_hash="x", role=Role.CUSTOMER,
        full_name="C D", phone=None, public_slug=None,
    ).value
    await repo.add(a)
    await repo.add(b)
    await db_session.flush()


@pytest.mark.asyncio
async def test_get_by_public_slug_returns_owner(db_session: AsyncSession):
    repo = UserRepository(db_session)
    owner = User.create(
        email="o@example.com", password_hash="x", role=Role.OWNER,
        full_name="O Owner", phone=None, public_slug="o-owner",
    ).value
    await repo.add(owner)
    await db_session.flush()

    found = await repo.get_by_public_slug("o-owner")
    assert found is not None
    assert found.id == owner.id

    missing = await repo.get_by_public_slug("nope")
    assert missing is None
