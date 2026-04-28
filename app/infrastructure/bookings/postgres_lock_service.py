from __future__ import annotations
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.bookings.lock import IBookingLockService


class PostgresBookingLockService(IBookingLockService):
    """Wraps Postgres pg_advisory_xact_lock keyed on a hash of resource_id.

    The lock is automatically released at TX commit/rollback (xact lock
    flavor). Caller must run inside a transaction; in FastAPI request
    handlers, this is the request-scoped session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"),
            {"k": self._hash_uuid(resource_id)},
        )
        try:
            yield None
        finally:
            # No-op: pg_advisory_xact_lock releases at TX commit/rollback.
            pass

    @staticmethod
    def _hash_uuid(uuid: UUID) -> int:
        # int.from_bytes with signed=True yields a value in
        # [-2**63, 2**63-1] which fits Postgres BIGINT for advisory locks.
        return int.from_bytes(uuid.bytes[:8], "big", signed=True)
