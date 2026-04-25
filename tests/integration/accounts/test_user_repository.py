from __future__ import annotations
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappings import user  # noqa: F401  (registers mapping)
from app.infrastructure.repositories.user_repository import UserRepository


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def make_user(email: str = "alice@example.com", role: Role = Role.CUSTOMER) -> User:
    r = User.create(
        email=email,
        password_hash="$argon2id$fake",
        role=role,
        full_name="Alice",
        phone="+5511999999999",
    )
    assert r.is_success
    return r.value


@pytest.mark.asyncio
async def test_add_and_get_by_id(session):
    repo = UserRepository(session)
    u = make_user()
    await repo.add(u)
    await session.commit()

    fetched = await repo.get_by_id(u.id)
    assert fetched is not None
    assert str(fetched.email) == "alice@example.com"
    assert fetched.role is Role.CUSTOMER
    assert fetched.full_name.value == "Alice"


@pytest.mark.asyncio
async def test_get_by_email_case_insensitive(session):
    repo = UserRepository(session)
    await repo.add(make_user("Alice@Example.com"))
    await session.commit()
    found = await repo.get_by_email("alice@example.com")
    assert found is not None
    assert str(found.email) == "alice@example.com"


@pytest.mark.asyncio
async def test_get_by_email_missing_returns_none(session):
    repo = UserRepository(session)
    assert await repo.get_by_email("nobody@example.com") is None


@pytest.mark.asyncio
async def test_update_role(session):
    repo = UserRepository(session)
    u = make_user(role=Role.CUSTOMER)
    await repo.add(u)
    await session.commit()

    u.set_role(Role.OWNER)
    await repo.update(u)
    await session.commit()

    fetched = await repo.get_by_id(u.id)
    assert fetched.role is Role.OWNER


@pytest.mark.asyncio
async def test_list_active_excludes_deactivated(session):
    repo = UserRepository(session)
    a = make_user("a@example.com")
    b = make_user("b@example.com")
    b.deactivate()
    await repo.add(a)
    await repo.add(b)
    await session.commit()

    rows = await repo.list_active()
    assert len(rows) == 1
    assert str(rows[0].email) == "a@example.com"
