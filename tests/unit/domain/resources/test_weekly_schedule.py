from __future__ import annotations
from datetime import time

from app.domain.resources.weekly_schedule import WeeklySchedule
from app.domain.shared.value_objects.time_window import TimeWindow
from app.domain.shared.weekday import Weekday


def _w(start_h: int, start_m: int, end_h: int, end_m: int) -> TimeWindow:
    r = TimeWindow.create(time(start_h, start_m), time(end_h, end_m))
    assert r.is_success
    return r.value


# --- happy paths ---

def test_create_empty_schedule():
    r = WeeklySchedule.create(slot_duration_minutes=60, days={})
    assert r.is_success
    sched = r.value
    assert sched.monday == ()
    assert sched.sunday == ()


def test_create_single_window_per_day():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 0, 22, 0)],
            Weekday.SATURDAY: [_w(9, 0, 23, 0)],
        },
    )
    assert r.is_success
    sched = r.value
    assert len(sched.monday) == 1
    assert sched.monday[0].start == time(8, 0)
    assert sched.tuesday == ()
    assert len(sched.saturday) == 1


def test_create_multiple_windows_per_day():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 0, 12, 0), _w(14, 0, 22, 0)],
        },
    )
    assert r.is_success
    sched = r.value
    assert len(sched.monday) == 2


def test_for_weekday_returns_windows():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.FRIDAY: [_w(18, 0, 23, 0)]},
    )
    sched = r.value
    assert sched.for_weekday(Weekday.FRIDAY) == (_w(18, 0, 23, 0),)
    assert sched.for_weekday(Weekday.MONDAY) == ()


# --- ordering / overlap / alignment ---

def test_create_rejects_unordered_windows():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(14, 0, 18, 0), _w(8, 0, 12, 0)],  # second starts before first
        },
    )
    assert r.is_failure
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[1]", WeeklySchedule.WINDOWS_NOT_ORDERED) in codes


def test_create_rejects_overlapping_windows():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 0, 14, 0), _w(13, 0, 22, 0)],  # 13:00 inside 8-14
        },
    )
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[1]", WeeklySchedule.WINDOWS_OVERLAP) in codes


def test_create_rejects_misaligned_start():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 30, 14, 0)]},  # 8:30 not aligned to 60min slots
    )
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[0]", WeeklySchedule.WINDOW_NOT_ALIGNED_TO_SLOT_GRID) in codes


def test_create_rejects_misaligned_duration():
    # 60-min slot, 8:00-13:30 = 330 minutes (not divisible by 60)
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={Weekday.MONDAY: [_w(8, 0, 13, 30)]},
    )
    assert r.is_failure
    codes = {(e.field, e.code) for e in r.details}
    assert ("days.monday[0]", WeeklySchedule.WINDOW_NOT_ALIGNED_TO_SLOT_GRID) in codes


def test_create_aggregates_errors_across_weekdays():
    r = WeeklySchedule.create(
        slot_duration_minutes=60,
        days={
            Weekday.MONDAY: [_w(8, 30, 14, 0)],   # misaligned
            Weekday.FRIDAY: [_w(18, 0, 22, 0), _w(20, 0, 23, 0)],  # overlap
        },
    )
    assert r.is_failure
    fields = {e.field for e in r.details}
    assert "days.monday[0]" in fields
    assert "days.friday[1]" in fields
