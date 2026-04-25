from __future__ import annotations
from typing import Protocol


class IPasswordHasher(Protocol):
    def hash(self, plaintext: str) -> str:
        """Return an opaque hash string. Algorithm + parameters are encoded inside the hash."""

    def verify(self, plaintext: str, hashed: str) -> bool:
        """Return True iff plaintext matches hashed. MUST be timing-safe."""

    def needs_rehash(self, hashed: str) -> bool:
        """Return True if the hash was produced with weaker parameters than current settings."""
