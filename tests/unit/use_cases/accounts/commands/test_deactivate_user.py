from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.commands.deactivate_user import (
    DeactivateUserCommand, DeactivateUserHandler,
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
async def test_deactivate_user():
    user = seed_user()
    repo = InMemoryUserRepository(seed=[user])
    handler = DeactivateUserHandler(repo)
    r = await handler.handle(DeactivateUserCommand(user_id=user.id))
    assert r.is_success
    refreshed = await repo.get_by_id(user.id)
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_deactivate_missing_user():
    repo = InMemoryUserRepository()
    handler = DeactivateUserHandler(repo)
    r = await handler.handle(DeactivateUserCommand(user_id=uuid4()))
    assert r.is_failure
    assert r.status_code == 404
