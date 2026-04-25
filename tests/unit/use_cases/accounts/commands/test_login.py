from __future__ import annotations
import pytest
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.use_cases.accounts.commands.login import LoginCommand, LoginHandler
from tests.unit.use_cases.accounts.fakes.in_memory_user_repository import InMemoryUserRepository
from tests.unit.use_cases.accounts.fakes.fake_password_hasher import FakePasswordHasher


class FakeJwtService:
    def __init__(self):
        self.last_user_id = None
        self.last_role = None

    def issue_pair(self, *, user_id, role):
        from app.domain.accounts.jwt_service import TokenPair
        self.last_user_id = user_id
        self.last_role = role
        return TokenPair(
            access_token=f"acc-{user_id}",
            refresh_token=f"ref-{user_id}",
            access_expires_in_seconds=1800,
        )

    def decode(self, token):
        raise NotImplementedError


def seed_user(*, email="alice@example.com", password="hunter2-strong",
              role=Role.CUSTOMER, is_active=True):
    h = FakePasswordHasher()
    r = User.create(
        email=email, password_hash=h.hash(password), role=role,
        full_name="Alice", phone=None,
    )
    u = r.value
    if not is_active:
        u.deactivate()
    return u


def make_handler(seed_users=()):
    repo = InMemoryUserRepository(seed=seed_users)
    hasher = FakePasswordHasher()
    jwt_svc = FakeJwtService()
    return LoginHandler(repo, hasher, jwt_svc), repo, hasher, jwt_svc


@pytest.mark.asyncio
async def test_login_success():
    user = seed_user()
    handler, _, _, jwt_svc = make_handler([user])
    r = await handler.handle(LoginCommand(email="alice@example.com", password="hunter2-strong"))
    assert r.is_success
    pair = r.value
    assert pair.access_token == f"acc-{user.id}"
    assert pair.user.email == "alice@example.com"
    assert jwt_svc.last_role is Role.CUSTOMER


@pytest.mark.asyncio
async def test_login_wrong_password():
    user = seed_user()
    handler, _, _, _ = make_handler([user])
    r = await handler.handle(LoginCommand(email="alice@example.com", password="wrong"))
    assert r.is_failure
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email():
    handler, _, _, _ = make_handler([])
    r = await handler.handle(LoginCommand(email="nobody@example.com", password="x"))
    assert r.is_failure
    assert r.status_code == 401  # same code as wrong password — don't leak existence


@pytest.mark.asyncio
async def test_login_unknown_email_and_wrong_password_return_identical_response():
    """Account-enumeration defense: callers must not be able to distinguish 'no such account'
    from 'wrong password'. Pin the contract so future refactors can't widen the gap."""
    existing = seed_user(email="alice@example.com", password="hunter2-strong")
    handler, _, _, _ = make_handler([existing])

    wrong_pw = await handler.handle(LoginCommand(
        email="alice@example.com", password="wrong",
    ))
    unknown = await handler.handle(LoginCommand(
        email="nobody@example.com", password="anything",
    ))

    assert wrong_pw.is_failure and unknown.is_failure
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.error == unknown.error  # exact message parity


@pytest.mark.asyncio
async def test_login_deactivated_account():
    user = seed_user(is_active=False)
    handler, _, _, _ = make_handler([user])
    r = await handler.handle(LoginCommand(email="alice@example.com", password="hunter2-strong"))
    assert r.is_failure
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_login_rehashes_legacy_hash_on_success():
    """Opportunistic-rehash path: if the stored hash predates current Argon2 params,
    a successful login should re-hash and persist the new hash."""
    h = FakePasswordHasher()
    # Seed with a "legacy" hash format that the FakePasswordHasher sees as needs_rehash.
    legacy_user_r = User.create(
        email="alice@example.com",
        password_hash="legacy:hunter2-strong",  # not the "fake:..." current format
        role=Role.CUSTOMER, full_name="Alice", phone=None,
    )
    user = legacy_user_r.value
    repo = InMemoryUserRepository(seed=[user])
    handler = LoginHandler(repo, h, FakeJwtService())

    # FakePasswordHasher.verify only accepts "fake:..." — so for this path to work,
    # we need a verify that accepts "legacy:..." too. Use a one-off subclass.
    class LegacyAcceptingHasher(FakePasswordHasher):
        def verify(self, plaintext: str, hashed: str) -> bool:
            return hashed in {f"fake:{plaintext}", f"legacy:{plaintext}"}

    handler = LoginHandler(repo, LegacyAcceptingHasher(), FakeJwtService())
    r = await handler.handle(LoginCommand(email="alice@example.com", password="hunter2-strong"))
    assert r.is_success

    persisted = await repo.get_by_email("alice@example.com")
    assert persisted.password_hash == "fake:hunter2-strong", (
        "expected opportunistic rehash to current 'fake:' format"
    )
