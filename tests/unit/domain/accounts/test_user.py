from __future__ import annotations
from app.domain.accounts.role import Role
from app.domain.accounts.user import User
from app.domain.shared.value_objects.name import Name


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
    assert u.full_name.value == "Alice Almeida"
    assert str(u.phone) == "+5511999999999"
    assert u.is_active is True


def test_create_user_no_phone():
    r = User.create(
        email="bob@example.com",
        password_hash="hash",
        role=Role.OWNER,
        full_name="Bob",
        phone=None,
        public_slug="bob",
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
    assert r.error is None
    assert r.details is not None
    assert any(e.field == "email" for e in r.details)


def test_user_full_name_is_name_vo():
    r = User.create(
        email="user@example.com",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
        role=Role.CUSTOMER,
        full_name="Maria da Silva",
        phone=None,
    )
    assert r.is_success
    assert isinstance(r.value.full_name, Name)
    assert r.value.full_name.value == "Maria da Silva"


def test_user_create_propagates_name_validation_error():
    r = User.create(
        email="user@example.com",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
        role=Role.CUSTOMER,
        full_name="",
        phone=None,
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("full_name", Name.NAME_CANNOT_BE_EMPTY) in codes


def test_user_create_propagates_name_max_length_error():
    r = User.create(
        email="user@example.com",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
        role=Role.CUSTOMER,
        full_name="a" * 501,
        phone=None,
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("full_name", Name.NAME_CANNOT_BE_GREATER_THAN_MAX_LENGTH) in codes


def test_create_user_blank_full_name():
    r = User.create(
        email="alice@example.com",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="   ",
        phone=None,
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("full_name", Name.NAME_CANNOT_BE_EMPTY) in codes


def test_user_create_aggregates_multiple_field_failures():
    """Spec §5.1: User.create emits one FieldError per failing field."""
    from app.domain.shared.value_objects.brazilian_phone import BrazilianPhone
    from app.domain.shared.value_objects.email import Email

    r = User.create(
        email="not-an-email",
        password_hash="",
        role=Role.CUSTOMER,
        full_name="",
        phone="abc",
    )
    assert r.is_failure
    assert r.error is None
    assert r.details is not None
    codes = {(e.field, e.code) for e in r.details}
    assert ("email", Email.EMAIL_INVALID_FORMAT) in codes
    assert ("full_name", Name.NAME_CANNOT_BE_EMPTY) in codes
    assert ("password_hash", "PasswordHashCannotBeEmpty") in codes
    assert ("phone", BrazilianPhone.PHONE_CONTAINS_INVALID_CHARACTERS) in codes


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


def test_owner_requires_public_slug():
    r = User.create(
        email="o@example.com",
        password_hash="hash",
        role=Role.OWNER,
        full_name="Joana Silva",
        phone=None,
        public_slug=None,
    )
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert User.PUBLIC_SLUG_REQUIRED_FOR_OWNER in codes


def test_non_owner_forbids_public_slug():
    r = User.create(
        email="c@example.com",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="Bruno Lima",
        phone=None,
        public_slug="bruno-lima",
    )
    assert r.is_failure
    codes = {e.code for e in r.details}
    assert User.PUBLIC_SLUG_FORBIDDEN_FOR_NON_OWNER in codes


def test_owner_accepts_valid_slug():
    r = User.create(
        email="o@example.com",
        password_hash="hash",
        role=Role.OWNER,
        full_name="Joana Silva",
        phone=None,
        public_slug="joana-silva",
    )
    assert r.is_success
    assert r.value.public_slug.value == "joana-silva"


def test_customer_accepts_no_slug():
    r = User.create(
        email="c@example.com",
        password_hash="hash",
        role=Role.CUSTOMER,
        full_name="Bruno Lima",
        phone=None,
        public_slug=None,
    )
    assert r.is_success
    assert r.value.public_slug is None
