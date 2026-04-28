from __future__ import annotations
from contextlib import asynccontextmanager
from uuid import UUID

from app.domain.bookings.lock import IBookingLockService


class FakeBookingLockService(IBookingLockService):
    """No-op acquire — single-thread unit tests don't need real serialization."""

    @asynccontextmanager
    async def acquire_for_resource(self, resource_id: UUID):
        yield None
