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
