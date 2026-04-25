from __future__ import annotations
from app.domain.shared.value_objects.slot_duration import SlotDuration


def test_slot_duration_accepts_allowed_values():
    for n in [30, 45, 60, 90, 120]:
        r = SlotDuration.create(n)
        assert r.is_success
        assert r.value.minutes == n


def test_slot_duration_rejects_unsupported():
    for bad in [10, 15, 25, 50, 75, 100, 150, 0, -30]:
        r = SlotDuration.create(bad)
        assert r.is_failure, f"expected failure for {bad}"
        assert r.error == SlotDuration.SLOT_DURATION_NOT_ALLOWED


def test_slot_duration_rejects_non_int():
    for bad in [None, 30.0, "60", True]:
        r = SlotDuration.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == SlotDuration.SLOT_DURATION_INVALID_TYPE


def test_slot_duration_allowed_set_exposed():
    assert SlotDuration.ALLOWED == frozenset({30, 45, 60, 90, 120})
