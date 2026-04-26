from __future__ import annotations
import os

# Set env vars before app.main is imported (get_settings() is called at module level).
os.environ.setdefault("BACKEND_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BACKEND_ENVIRONMENT", "test")
os.environ.setdefault("BACKEND_JWT_SECRET_KEY", "test-jwt-secret-fixed-for-determinism")
os.environ.setdefault("BACKEND_ARGON2_TIME_COST", "1")
os.environ.setdefault("BACKEND_ARGON2_MEMORY_COST_KIB", "8")
os.environ.setdefault("BACKEND_ARGON2_PARALLELISM", "1")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.infrastructure.db import session as session_mod
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappings import owner_subscription  # noqa: F401
from app.infrastructure.db.mappings import resource  # noqa: F401
from app.infrastructure.db.mappings import resource_type  # noqa: F401
from app.infrastructure.db.mappings import user  # noqa: F401
from app.infrastructure.db.mappings.user import UserModel
from app.main import app


@pytest_asyncio.fixture
async def client():
    # httpx ASGITransport does NOT run lifespan by default — we init DB manually.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_mod._engine = engine
    session_mod._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await engine.dispose()
    session_mod._engine = None
    session_mod._sessionmaker = None


@pytest_asyncio.fixture
async def db_session(client):
    """An AsyncSession that shares the same in-memory engine as ``client``.

    ``client`` must be requested first so that ``session_mod._sessionmaker``
    is already pointing at the test engine before we open a session here.
    The fixture depends on ``client`` (not the other way around) so the
    fixture graph is: client → db_session → test.
    """
    assert session_mod._sessionmaker is not None
    async with session_mod._sessionmaker() as s:
        yield s


@pytest_asyncio.fixture
async def http_client(client):
    """Alias for ``client``. The catalog e2e tests use this name."""
    return client


async def _register_and_login(
    client: AsyncClient, *, email: str, password: str, role: str = "customer",
) -> str:
    register = await client.post("/v1/auth/register", json={
        "email": email, "password": password, "role": role,
        "full_name": "Test User", "phone": None,
    })
    assert register.status_code == 201, register.text
    login = await client.post("/v1/auth/login", json={
        "email": email, "password": password,
    })
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest_asyncio.fixture
async def customer_token(client) -> str:
    return await _register_and_login(
        client, email="customer@example.com", password="hunter2-strong",
    )


@pytest_asyncio.fixture
async def admin_token(client) -> str:
    # Public registration rejects role=admin. Register as customer, then promote
    # the row to admin directly in the DB and login again.
    email = "admin@example.com"
    password = "hunter2-strong"
    register = await client.post("/v1/auth/register", json={
        "email": email, "password": password, "role": "customer",
        "full_name": "Admin User", "phone": None,
    })
    assert register.status_code == 201, register.text

    assert session_mod._sessionmaker is not None
    async with session_mod._sessionmaker() as s:
        await s.execute(
            update(UserModel).where(UserModel.email == email).values(role="admin")
        )
        await s.commit()

    login = await client.post("/v1/auth/login", json={
        "email": email, "password": password,
    })
    assert login.status_code == 200, login.text
    return login.json()["access_token"]
