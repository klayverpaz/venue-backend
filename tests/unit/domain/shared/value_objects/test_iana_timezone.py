from __future__ import annotations
from app.domain.shared.value_objects.iana_timezone import IanaTimezone


def test_iana_tz_accepts_sao_paulo():
    r = IanaTimezone.create("America/Sao_Paulo")
    assert r.is_success
    assert r.value.value == "America/Sao_Paulo"
    assert str(r.value) == "America/Sao_Paulo"


def test_iana_tz_accepts_utc():
    r = IanaTimezone.create("UTC")
    assert r.is_success


def test_iana_tz_strips_whitespace():
    r = IanaTimezone.create("  America/Sao_Paulo  ")
    assert r.is_success
    assert r.value.value == "America/Sao_Paulo"


def test_iana_tz_rejects_unknown():
    r = IanaTimezone.create("Mars/Olympus")
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_UNKNOWN


def test_iana_tz_rejects_empty():
    r = IanaTimezone.create("")
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY


def test_iana_tz_rejects_none():
    r = IanaTimezone.create(None)
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY


def test_iana_tz_rejects_non_string():
    r = IanaTimezone.create(123)
    assert r.is_failure
    assert r.error == IanaTimezone.IANA_TIMEZONE_CANNOT_BE_EMPTY


def test_iana_tz_to_zoneinfo_returns_valid_object():
    from zoneinfo import ZoneInfo
    tz = IanaTimezone.create("America/Sao_Paulo").value
    assert isinstance(tz.to_zoneinfo(), ZoneInfo)
