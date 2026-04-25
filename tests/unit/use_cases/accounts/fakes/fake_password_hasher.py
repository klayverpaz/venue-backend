from __future__ import annotations
from app.domain.accounts.password_hasher import IPasswordHasher


class FakePasswordHasher(IPasswordHasher):
    """Reversible fake: hash(x) == 'fake:' + x. Use in handler tests."""

    def hash(self, plaintext: str) -> str:
        return f"fake:{plaintext}"

    def verify(self, plaintext: str, hashed: str) -> bool:
        return hashed == f"fake:{plaintext}"

    def needs_rehash(self, hashed: str) -> bool:
        return not hashed.startswith("fake:")
