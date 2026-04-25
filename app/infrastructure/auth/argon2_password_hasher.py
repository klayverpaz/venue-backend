from __future__ import annotations
from argon2 import PasswordHasher as _ArgonHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.domain.accounts.password_hasher import IPasswordHasher


class Argon2PasswordHasher(IPasswordHasher):
    def __init__(
        self,
        *,
        time_cost: int,
        memory_cost_kib: int,
        parallelism: int,
    ) -> None:
        self._impl = _ArgonHasher(
            time_cost=time_cost,
            memory_cost=memory_cost_kib,
            parallelism=parallelism,
        )

    def hash(self, plaintext: str) -> str:
        return self._impl.hash(plaintext)

    def verify(self, plaintext: str, hashed: str) -> bool:
        try:
            return self._impl.verify(hashed, plaintext)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hashed: str) -> bool:
        try:
            return self._impl.check_needs_rehash(hashed)
        except InvalidHashError:
            return True
