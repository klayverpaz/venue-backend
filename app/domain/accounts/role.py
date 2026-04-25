from __future__ import annotations
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    OWNER = "owner"
    CUSTOMER = "customer"

    def is_self_registerable(self) -> bool:
        return self is Role.OWNER or self is Role.CUSTOMER
