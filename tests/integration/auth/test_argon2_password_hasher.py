from __future__ import annotations
from app.infrastructure.auth.argon2_password_hasher import Argon2PasswordHasher


def test_hash_and_verify_round_trip():
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    h = hasher.hash("hunter2")
    assert h.startswith("$argon2")
    assert hasher.verify("hunter2", h) is True
    assert hasher.verify("wrong", h) is False


def test_two_hashes_of_same_plaintext_differ():
    hasher = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    a = hasher.hash("hunter2")
    b = hasher.hash("hunter2")
    assert a != b  # salt is random


def test_needs_rehash_detects_weaker_params():
    weak = Argon2PasswordHasher(time_cost=1, memory_cost_kib=8, parallelism=1)
    strong = Argon2PasswordHasher(time_cost=3, memory_cost_kib=64, parallelism=1)
    h = weak.hash("hunter2")
    assert strong.needs_rehash(h) is True
    assert weak.needs_rehash(h) is False
