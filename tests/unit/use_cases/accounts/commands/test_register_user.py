from __future__ import annotations
import pytest
from app.core.config import Settings
from app.domain.accounts.role import Role
from app.use_cases.accounts.commands.register_user import (
    RegisterUserCommand, RegisterUserHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher
from tests.unit.use_cases.subscriptions.fakes.in_memory_subscription_repository import (
    InMemorySubscriptionRepository,
)


def make_handler():
    repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()
    subs = InMemorySubscriptionRepository()
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        trial_duration_days=3,
    )
    return RegisterUserHandler(repo, hasher, subs, settings), repo, hasher, subs


@pytest.mark.asyncio
async def test_register_customer_success():
    handler, repo, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="alice@example.com",
        password="hunter2-strong",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    ))
    assert r.is_success
    dto = r.value
    assert dto.email == "alice@example.com"
    assert dto.role is Role.CUSTOMER
    # Password is hashed, not stored
    persisted = await repo.get_by_email("alice@example.com")
    assert persisted.password_hash == "fake:hunter2-strong"


@pytest.mark.asyncio
async def test_register_owner_success():
    handler, _, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="bob@example.com",
        password="hunter2-strong",
        role=Role.OWNER,
        full_name="Bob",
        phone="+5511999999999",
        public_slug="bob",
    ))
    assert r.is_success
    assert r.value.role is Role.OWNER


@pytest.mark.asyncio
async def test_register_admin_rejected():
    handler, _, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="admin@example.com",
        password="hunter2-strong",
        role=Role.ADMIN,
        full_name="Adm",
        phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 403
    assert "admin" in r.error.lower()


@pytest.mark.asyncio
async def test_register_email_collision():
    handler, repo, _, _ = make_handler()
    await handler.handle(RegisterUserCommand(
        email="alice@example.com", password="hunter2-strong",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    r = await handler.handle(RegisterUserCommand(
        email="alice@example.com", password="other-pw",
        role=Role.CUSTOMER, full_name="Alice2", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password():
    handler, _, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="alice@example.com", password="abc",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
    assert "senha" in r.error.lower() or "password" in r.error.lower()


@pytest.mark.asyncio
async def test_register_invalid_email():
    handler, _, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="not-an-email", password="hunter2-strong",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_user_propagates_user_create_details():
    """User.create emits failure_many; the handler must preserve r.details."""
    handler, _, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="not-an-email", password="hunter2-strong",
        role=Role.CUSTOMER, full_name="", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("email", "EmailInvalidFormat") in codes
    assert ("full_name", "NameCannotBeEmpty") in codes


@pytest.mark.asyncio
async def test_register_owner_creates_trialing_subscription():
    handler, _repo, _hasher, subs = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="newowner@example.com",
        password="hunter2-strong",
        role=Role.OWNER,
        full_name="Owner",
        phone=None,
        public_slug="owner",
    ))
    assert r.is_success
    sub = await subs.get_by_owner_id(r.value.id)
    assert sub is not None
    assert sub.status.value == "TRIALING"
    assert sub.trial_ends_at is not None


@pytest.mark.asyncio
async def test_register_customer_does_not_create_subscription():
    handler, _repo, _hasher, subs = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="customer2@example.com",
        password="hunter2-strong",
        role=Role.CUSTOMER,
        full_name="C",
        phone=None,
    ))
    assert r.is_success
    sub = await subs.get_by_owner_id(r.value.id)
    assert sub is None


@pytest.mark.asyncio
async def test_register_owner_trial_window_uses_config_value():
    from datetime import timedelta
    handler, _repo, _hasher, subs = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="windowowner@example.com",
        password="hunter2-strong",
        role=Role.OWNER,
        full_name="Owner",
        phone=None,
        public_slug="window-owner",
    ))
    sub = await subs.get_by_owner_id(r.value.id)
    delta = sub.trial_ends_at - sub.status_changed_at
    assert delta == timedelta(days=3)
