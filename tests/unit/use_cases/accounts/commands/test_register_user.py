from __future__ import annotations
import pytest
from app.domain.accounts.role import Role
from app.use_cases.accounts.commands.register_user import (
    RegisterUserCommand, RegisterUserHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


def make_handler():
    repo = InMemoryUserRepository()
    hasher = FakePasswordHasher()
    return RegisterUserHandler(repo, hasher), repo, hasher


@pytest.mark.asyncio
async def test_register_customer_success():
    handler, repo, _ = make_handler()
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
    handler, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="bob@example.com",
        password="hunter2-strong",
        role=Role.OWNER,
        full_name="Bob",
        phone="+5511999999999",
    ))
    assert r.is_success
    assert r.value.role is Role.OWNER


@pytest.mark.asyncio
async def test_register_admin_rejected():
    handler, _, _ = make_handler()
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
    handler, repo, _ = make_handler()
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
    handler, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="alice@example.com", password="abc",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 422
    assert "senha" in r.error.lower() or "password" in r.error.lower()


@pytest.mark.asyncio
async def test_register_invalid_email():
    handler, _, _ = make_handler()
    r = await handler.handle(RegisterUserCommand(
        email="not-an-email", password="hunter2-strong",
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    ))
    assert r.is_failure
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_register_user_propagates_user_create_details():
    """User.create emits failure_many; the handler must preserve r.details."""
    handler, _, _ = make_handler()
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
