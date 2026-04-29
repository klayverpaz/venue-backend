"""Bootstrap an admin user directly in the DB.

Usage (inside the app container):
    docker compose exec app python -m scripts.bootstrap_admin

Reads ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_FULL_NAME from env (with dev defaults).
Idempotent: re-running with the same email is a no-op.

Stand-in for Plan 10's seed step until that ships.
"""
from __future__ import annotations
import asyncio
import os

from app.core.config import get_settings
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.db.session import dispose_engine, init_engine
from app.infrastructure.repositories.user_repository import UserRepository
from sqlalchemy.ext.asyncio import async_sessionmaker


async def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin@venue.app")
    password = os.environ.get("ADMIN_PASSWORD", "AdminDev!2026")
    full_name = os.environ.get("ADMIN_FULL_NAME", "Venue Admin")

    settings = get_settings()
    engine = init_engine()
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    hasher = Argon2PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost_kib=settings.argon2_memory_cost_kib,
        parallelism=settings.argon2_parallelism,
    )

    try:
        async with sessionmaker() as session:
            repo = UserRepository(session)
            existing = await repo.get_by_email(email)
            if existing is not None:
                print(f"[bootstrap_admin] admin already exists (id={existing.id}, email={email}); no-op.")
                return

            result = User.create(
                email=email,
                password_hash=hasher.hash(password),
                role=Role.ADMIN,
                full_name=full_name,
                phone=None,
                public_slug=None,
            )
            if result.is_failure:
                raise RuntimeError(f"User.create rejected admin payload: {result.error} {result.details}")

            await repo.add(result.value)
            await session.commit()
            print(f"[bootstrap_admin] created admin id={result.value.id} email={email}")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
