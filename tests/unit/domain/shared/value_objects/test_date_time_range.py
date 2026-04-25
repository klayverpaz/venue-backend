from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.domain.shared.value_objects.date_time_range import DateTimeRange


def test_date_time_range_create_success_utc():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, end)
    assert r.is_success
    assert r.value.start_at == start
    assert r.value.end_at == end


def test_date_time_range_accepts_zoneinfo_utc():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=ZoneInfo("UTC"))
    end = datetime(2026, 5, 1, 16, 0, tzinfo=ZoneInfo("UTC"))
    r = DateTimeRange.create(start, end)
    assert r.is_success


def test_date_time_range_rejects_naive_datetime():
    start = datetime(2026, 5, 1, 14, 0)
    end = datetime(2026, 5, 1, 16, 0)
    r = DateTimeRange.create(start, end)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_NOT_TZ_AWARE


def test_date_time_range_rejects_non_utc_offset():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    end = datetime(2026, 5, 1, 16, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    r = DateTimeRange.create(start, end)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_NOT_UTC


def test_date_time_range_rejects_start_equals_end():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, start)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END


def test_date_time_range_rejects_start_after_end():
    start = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, end)
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_START_MUST_BE_BEFORE_END


def test_date_time_range_rejects_invalid_type():
    r = DateTimeRange.create("2026-05-01T14:00:00Z", "2026-05-01T16:00:00Z")
    assert r.is_failure
    assert r.error == DateTimeRange.DATE_TIME_RANGE_INVALID_TYPE


def test_date_time_range_duration_minutes():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 16, 30, tzinfo=timezone.utc)
    r = DateTimeRange.create(start, end).value
    assert r.duration_minutes() == 150


def test_date_time_range_overlaps():
    a = DateTimeRange.create(
        datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc),
    ).value
    b_overlap = DateTimeRange.create(
        datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc),
    ).value
    b_disjoint = DateTimeRange.create(
        datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 1, 17, 0, tzinfo=timezone.utc),
    ).value
    assert a.overlaps(b_overlap) is True
    assert a.overlaps(b_disjoint) is False
    assert b_disjoint.overlaps(a) is False
