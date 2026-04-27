from __future__ import annotations
from app.domain.shared.weekday import Weekday


def test_weekday_values():
    assert Weekday.MONDAY.value == "MONDAY"
    assert Weekday.TUESDAY.value == "TUESDAY"
    assert Weekday.WEDNESDAY.value == "WEDNESDAY"
    assert Weekday.THURSDAY.value == "THURSDAY"
    assert Weekday.FRIDAY.value == "FRIDAY"
    assert Weekday.SATURDAY.value == "SATURDAY"
    assert Weekday.SUNDAY.value == "SUNDAY"


def test_weekday_is_str_enum():
    # str enum so JSON serialization is the value directly.
    assert Weekday.MONDAY == "MONDAY"
    assert isinstance(Weekday.MONDAY, str)


def test_weekday_count():
    assert len(list(Weekday)) == 7


import pytest


def test_weekday_from_iso_monday_to_sunday():
    assert Weekday.from_iso(1) is Weekday.MONDAY
    assert Weekday.from_iso(2) is Weekday.TUESDAY
    assert Weekday.from_iso(3) is Weekday.WEDNESDAY
    assert Weekday.from_iso(4) is Weekday.THURSDAY
    assert Weekday.from_iso(5) is Weekday.FRIDAY
    assert Weekday.from_iso(6) is Weekday.SATURDAY
    assert Weekday.from_iso(7) is Weekday.SUNDAY


def test_weekday_from_iso_rejects_out_of_range():
    with pytest.raises(ValueError):
        Weekday.from_iso(0)
    with pytest.raises(ValueError):
        Weekday.from_iso(8)
