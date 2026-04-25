from __future__ import annotations
from app.domain.accounts.role import Role
from app.domain.accounts.user import User


def test_create_user_success():
    r = User.create(
        email="alice@example.com",
        password_hash="$argon2id$...",
        role=Role.CUSTOMER,
        full_name="Alice Almeida",
        phone="+5511999999999",
    )
    assert r.is_success
    u = r.value
    assert str(u.email) == "alice@example.com"
    assert u.password_hash == "$argon2id$..."
    assert u.role is Role.CUSTOMER
    assert u.full_name == "Alice Almeida"
    assert str(u.phone) == "+5511999999999"
    assert u.is_active is True


def test_create_user_no_phone():
    r = User.create(
        email="bob@example.com",
        password_hash="hash",
        role=Role.OWNER,
        full_name="Bob",
        phone=None,
    )
    assert r.is_success
    assert r.value.phone is None


def test_create_user_invalid_email():
    r = User.create(
        email="not-an-email",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="x",
        phone=None,
    )
    assert r.is_failure
    assert "email" in r.error.lower()


def test_create_user_blank_full_name():
    r = User.create(
        email="alice@example.com",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="   ",
        phone=None,
    )
    assert r.is_failure
    assert "full_name" in r.error or "nome" in r.error.lower()


def test_change_password_hash_updates_timestamp():
    r = User.create(
        email="alice@example.com",
        password_hash="old",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    )
    u = r.value
    before = u.updated_at
    u.change_password_hash("new")
    assert u.password_hash == "new"
    assert u.updated_at > before


def test_promote_role_admin_only_called_via_handler():
    """Domain just supports the mutation; the admin-only invariant is enforced at the handler level."""
    r = User.create(
        email="alice@example.com",
        password_hash="h",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    )
    u = r.value
    before = u.updated_at
    u.set_role(Role.OWNER)
    assert u.role is Role.OWNER
    assert u.updated_at > before


def test_deactivate_and_reactivate():
    r = User.create(
        email="alice@example.com",
        password_hash="h",
        role=Role.CUSTOMER,
        full_name="Alice",
        phone=None,
    )
    u = r.value
    u.deactivate()
    assert u.is_active is False
    u.activate()
    assert u.is_active is True
