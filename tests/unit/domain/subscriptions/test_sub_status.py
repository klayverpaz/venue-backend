from app.domain.subscriptions.sub_status import SubStatus


def test_sub_status_values():
    assert SubStatus.ACTIVE.value == "ACTIVE"
    assert SubStatus.TRIALING.value == "TRIALING"
    assert SubStatus.PAST_DUE.value == "PAST_DUE"
    assert SubStatus.INACTIVE.value == "INACTIVE"


def test_sub_status_active_is_operational():
    assert SubStatus.ACTIVE.is_operational() is True


def test_sub_status_trialing_is_operational():
    assert SubStatus.TRIALING.is_operational() is True


def test_sub_status_past_due_is_not_operational():
    assert SubStatus.PAST_DUE.is_operational() is False


def test_sub_status_inactive_is_not_operational():
    assert SubStatus.INACTIVE.is_operational() is False
