from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from uuid import UUID

from app.domain.bookings.lock import IBookingLockService


class InMemoryBookingLockService(IBookingLockService):
    """asyncio.Lock per resource_id in a process-local dict.

    Sufficient for SQLite-backed integration tests and unit tests; NOT
    suitable for production multi-instance deployments.
    """

    def __init__(self) -> None:
        self._locks: dict[UUID, asyncio.Lock] = {}

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        lock = self._locks.setdefault(resource_id, asyncio.Lock())
        async with lock:
            yield None
