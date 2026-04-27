from __future__ import annotations
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID


class IBookingLockService(Protocol):
    """Per-resource lock acquired during RequestBookingHandler natural-dedup
    + ApproveBookingHandler approval transaction. Implementation is
    dialect-specific:

    - PostgresBookingLockService: pg_advisory_xact_lock(hash(uuid)) — released
      automatically at TX commit/rollback.
    - InMemoryBookingLockService: asyncio.Lock keyed by resource_id in a
      module-level dict. Single-process only; sufficient for test isolation.
    """

    def acquire_for_resource(
        self, resource_id: UUID,
    ) -> AbstractAsyncContextManager[None]: ...
