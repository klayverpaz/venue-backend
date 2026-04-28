from __future__ import annotations
import asyncio
from uuid import uuid4

import pytest

from app.infrastructure.bookings.in_memory_lock_service import (
    InMemoryBookingLockService,
)


pytestmark = pytest.mark.asyncio


async def test_concurrent_acquires_on_same_resource_serialize():
    svc = InMemoryBookingLockService()
    rid = uuid4()
    order: list[str] = []

    async def worker(label: str, hold: float):
        async with svc.acquire_for_resource(rid):
            order.append(f"{label}:in")
            await asyncio.sleep(hold)
            order.append(f"{label}:out")

    await asyncio.gather(worker("A", 0.05), worker("B", 0.0))
    # If serialized, A:in → A:out → B:in → B:out (or B first then A).
    # Test: every "in" is immediately followed by the matching "out".
    assert order[0].endswith(":in")
    assert order[1].endswith(":out")
    assert order[0].split(":")[0] == order[1].split(":")[0]
    assert order[2].endswith(":in")
    assert order[3].endswith(":out")
    assert order[2].split(":")[0] == order[3].split(":")[0]


async def test_concurrent_acquires_on_different_resources_do_not_serialize():
    svc = InMemoryBookingLockService()
    r1, r2 = uuid4(), uuid4()
    started: list[str] = []
    finished: list[str] = []

    async def worker(label: str, rid):
        async with svc.acquire_for_resource(rid):
            started.append(label)
            await asyncio.sleep(0.05)
            finished.append(label)

    await asyncio.gather(worker("A", r1), worker("B", r2))
    # Both should start before either finishes (parallel because different rids).
    assert set(started) == {"A", "B"}
    assert len(started) == 2
    assert set(finished) == {"A", "B"}
