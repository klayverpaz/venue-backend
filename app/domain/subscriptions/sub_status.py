from __future__ import annotations
from enum import Enum


class SubStatus(str, Enum):
    """Lifecycle states of an OwnerSubscription.

    ACTIVE / TRIALING are operational (resources show in public listings,
    bookings can be approved). PAST_DUE / INACTIVE are non-operational.
    """

    ACTIVE = "ACTIVE"
    TRIALING = "TRIALING"
    PAST_DUE = "PAST_DUE"
    INACTIVE = "INACTIVE"

    def is_operational(self) -> bool:
        return self in {SubStatus.ACTIVE, SubStatus.TRIALING}
