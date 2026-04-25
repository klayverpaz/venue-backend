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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.infrastructure.db import session as session_mod
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappings import user  # noqa: F401
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
