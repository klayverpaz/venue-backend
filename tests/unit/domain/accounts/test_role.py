from app.domain.accounts.role import Role


def test_role_values():
    assert Role.ADMIN.value == "admin"
    assert Role.OWNER.value == "owner"
    assert Role.CUSTOMER.value == "customer"


def test_role_from_string():
    assert Role("admin") is Role.ADMIN
    assert Role("owner") is Role.OWNER
    assert Role("customer") is Role.CUSTOMER


def test_role_self_registerable():
    assert Role.OWNER.is_self_registerable() is True
    assert Role.CUSTOMER.is_self_registerable() is True
    assert Role.ADMIN.is_self_registerable() is False
