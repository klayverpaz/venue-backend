from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.queries.get_user_by_id import (
    GetUserByIdQuery, GetUserByIdHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


def seed_user():
    h = FakePasswordHasher()
    r = User.create(
        email="alice@example.com", password_hash=h.hash("pw"),
        role=Role.OWNER, full_name="Alice", phone=None,
        public_slug="alice",
    )
    return r.value


@pytest.mark.asyncio
async def test_get_existing():
    user = seed_user()
    repo = InMemoryUserRepository(seed=[user])
    handler = GetUserByIdHandler(repo)
    r = await handler.handle(GetUserByIdQuery(user_id=user.id))
    assert r.is_success
    assert r.value.email == "alice@example.com"


@pytest.mark.asyncio
async def test_get_missing():
    repo = InMemoryUserRepository()
    handler = GetUserByIdHandler(repo)
    r = await handler.handle(GetUserByIdQuery(user_id=uuid4()))
    assert r.is_failure
    assert r.status_code == 404
