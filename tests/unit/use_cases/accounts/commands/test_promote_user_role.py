from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.commands.promote_user_role import (
    PromoteUserRoleCommand, PromoteUserRoleHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


def seed_user(role=Role.CUSTOMER):
    h = FakePasswordHasher()
    slug = "alice" if role is Role.OWNER else None
    r = User.create(
        email="alice@example.com", password_hash=h.hash("pw"),
        role=role, full_name="Alice", phone=None,
        public_slug=slug,
    )
    return r.value


@pytest.mark.asyncio
async def test_promote_customer_to_owner():
    user = seed_user(Role.CUSTOMER)
    repo = InMemoryUserRepository(seed=[user])
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(
        user_id=user.id, new_role=Role.OWNER,
    ))
    assert r.is_success
    refreshed = await repo.get_by_id(user.id)
    assert refreshed.role is Role.OWNER


@pytest.mark.asyncio
async def test_promote_missing_user():
    repo = InMemoryUserRepository()
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(user_id=uuid4(), new_role=Role.OWNER))
    assert r.is_failure
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_promote_to_admin_allowed():
    """The handler accepts ADMIN — only the route-level guard restricts who can call this handler."""
    user = seed_user(Role.OWNER)
    repo = InMemoryUserRepository(seed=[user])
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(user_id=user.id, new_role=Role.ADMIN))
    assert r.is_success
    refreshed = await repo.get_by_id(user.id)
    assert refreshed.role is Role.ADMIN


@pytest.mark.asyncio
async def test_promote_same_role_is_noop_but_succeeds():
    user = seed_user(Role.OWNER)
    repo = InMemoryUserRepository(seed=[user])
    handler = PromoteUserRoleHandler(repo)
    r = await handler.handle(PromoteUserRoleCommand(user_id=user.id, new_role=Role.OWNER))
    assert r.is_success
