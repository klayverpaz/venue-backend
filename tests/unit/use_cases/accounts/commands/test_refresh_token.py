from __future__ import annotations
import pytest
from uuid import uuid4
from app.domain.accounts.jwt_service import TokenClaims, TokenPair
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.shared.result import Result
from app.use_cases.accounts.commands.refresh_token import (
    RefreshTokenCommand, RefreshTokenHandler,
)
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


class StubJwtService:
    def __init__(self, *, decode_result: Result[TokenClaims]):
        self._decode_result = decode_result

    def issue_pair(self, *, user_id, role):
        return TokenPair(
            access_token=f"new-acc-{user_id}",
            refresh_token=f"new-ref-{user_id}",
            access_expires_in_seconds=1800,
        )

    def decode(self, token):
        return self._decode_result


def seed_active_user(role=Role.CUSTOMER):
    h = FakePasswordHasher()
    r = User.create(
        email="alice@example.com", password_hash=h.hash("hunter2-strong"),
        role=role, full_name="Alice", phone=None,
    )
    return r.value


@pytest.mark.asyncio
async def test_refresh_success():
    user = seed_active_user()
    repo = InMemoryUserRepository(seed=[user])
    jwt_svc = StubJwtService(decode_result=Result.success(
        TokenClaims(user_id=user.id, role=user.role, type="refresh")
    ))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_success
    assert r.value.access_token == f"new-acc-{user.id}"
    assert r.value.user.email == "alice@example.com"


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected():
    user = seed_active_user()
    repo = InMemoryUserRepository(seed=[user])
    jwt_svc = StubJwtService(decode_result=Result.success(
        TokenClaims(user_id=user.id, role=user.role, type="access"),
    ))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_failure
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token():
    repo = InMemoryUserRepository()
    jwt_svc = StubJwtService(decode_result=Result.failure("expired", status_code=401))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_failure
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_user_deactivated_after_token_issued():
    user = seed_active_user()
    user.deactivate()
    repo = InMemoryUserRepository(seed=[user])
    jwt_svc = StubJwtService(decode_result=Result.success(
        TokenClaims(user_id=user.id, role=user.role, type="refresh")
    ))
    handler = RefreshTokenHandler(repo, jwt_svc)
    r = await handler.handle(RefreshTokenCommand(refresh_token="ignored"))
    assert r.is_failure
    assert r.status_code == 403
