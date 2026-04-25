from __future__ import annotations
import time
from uuid import uuid4
from app.domain.accounts.role import Role
from app.infrastructure.auth.jose_jwt_service import JoseJwtService


def make_service(*, access_seconds: int = 60, refresh_seconds: int = 600):
    return JoseJwtService(
        secret_key="test-secret",
        algorithm="HS256",
        access_token_expires_seconds=access_seconds,
        refresh_token_expires_seconds=refresh_seconds,
    )


def test_issue_and_decode_access_token():
    svc = make_service()
    user_id = uuid4()
    pair = svc.issue_pair(user_id=user_id, role=Role.OWNER)
    assert pair.token_type == "bearer"
    assert pair.access_expires_in_seconds == 60
    r = svc.decode(pair.access_token)
    assert r.is_success
    claims = r.value
    assert claims.user_id == user_id
    assert claims.role is Role.OWNER
    assert claims.type == "access"


def test_decode_refresh_token():
    svc = make_service()
    user_id = uuid4()
    pair = svc.issue_pair(user_id=user_id, role=Role.CUSTOMER)
    r = svc.decode(pair.refresh_token)
    assert r.is_success
    assert r.value.type == "refresh"


def test_decode_invalid_signature_fails():
    a = JoseJwtService(secret_key="A", algorithm="HS256",
                      access_token_expires_seconds=60, refresh_token_expires_seconds=600)
    b = JoseJwtService(secret_key="B", algorithm="HS256",
                      access_token_expires_seconds=60, refresh_token_expires_seconds=600)
    pair = a.issue_pair(user_id=uuid4(), role=Role.CUSTOMER)
    r = b.decode(pair.access_token)
    assert r.is_failure
    assert "signature" in r.error.lower() or "invalid" in r.error.lower()


def test_decode_expired_fails():
    svc = make_service(access_seconds=1, refresh_seconds=1)
    pair = svc.issue_pair(user_id=uuid4(), role=Role.CUSTOMER)
    time.sleep(2)
    r = svc.decode(pair.access_token)
    assert r.is_failure
    assert "expir" in r.error.lower()


def test_decode_garbage_fails():
    svc = make_service()
    r = svc.decode("not-a-jwt")
    assert r.is_failure


def test_two_pairs_for_same_user_have_different_tokens():
    svc = make_service()
    uid = uuid4()
    a = svc.issue_pair(user_id=uid, role=Role.OWNER)
    time.sleep(1.1)  # iat resolution is 1s
    b = svc.issue_pair(user_id=uid, role=Role.OWNER)
    assert a.access_token != b.access_token
