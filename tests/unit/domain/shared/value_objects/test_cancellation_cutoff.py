from __future__ import annotations
from app.domain.shared.value_objects.cancellation_cutoff import CancellationCutoff


def test_cutoff_accepts_zero():
    r = CancellationCutoff.create(0)
    assert r.is_success
    assert r.value.hours == 0


def test_cutoff_accepts_typical_24():
    r = CancellationCutoff.create(24)
    assert r.is_success
    assert r.value.hours == 24


def test_cutoff_accepts_max_168():
    r = CancellationCutoff.create(168)
    assert r.is_success


def test_cutoff_rejects_negative():
    r = CancellationCutoff.create(-1)
    assert r.is_failure
    assert r.error == CancellationCutoff.CANCELLATION_CUTOFF_OUT_OF_RANGE


def test_cutoff_rejects_above_max():
    r = CancellationCutoff.create(169)
    assert r.is_failure
    assert r.error == CancellationCutoff.CANCELLATION_CUTOFF_OUT_OF_RANGE


def test_cutoff_rejects_non_int():
    for bad in [None, 24.0, "24", True]:
        r = CancellationCutoff.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == CancellationCutoff.CANCELLATION_CUTOFF_INVALID_TYPE
