from __future__ import annotations
from datetime import time
from app.domain.shared.value_objects.time_window import TimeWindow


def test_time_window_create_success():
    r = TimeWindow.create(time(8, 0), time(18, 0))
    assert r.is_success
    assert r.value.start == time(8, 0)
    assert r.value.end == time(18, 0)


def test_time_window_rejects_start_equals_end():
    r = TimeWindow.create(time(8, 0), time(8, 0))
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END


def test_time_window_rejects_start_after_end():
    r = TimeWindow.create(time(18, 0), time(8, 0))
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END


def test_time_window_rejects_invalid_type():
    r = TimeWindow.create("08:00", "18:00")
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_INVALID_TYPE


def test_time_window_rejects_none():
    r = TimeWindow.create(None, None)
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_INVALID_TYPE


def test_time_window_duration_minutes():
    w = TimeWindow.create(time(8, 0), time(10, 30)).value
    assert w.duration_minutes() == 150


def test_time_window_duration_minutes_seconds_dropped():
    w = TimeWindow.create(time(8, 0, 0), time(8, 30, 0)).value
    assert w.duration_minutes() == 30


def test_time_window_equality_by_value():
    a = TimeWindow.create(time(8, 0), time(18, 0)).value
    b = TimeWindow.create(time(8, 0), time(18, 0)).value
    assert a == b
    assert hash(a) == hash(b)


def test_time_window_overnight_explicitly_rejected():
    r = TimeWindow.create(time(22, 0), time(2, 0))
    assert r.is_failure
    assert r.error == TimeWindow.TIME_WINDOW_START_MUST_BE_BEFORE_END
