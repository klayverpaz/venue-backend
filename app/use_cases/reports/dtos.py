from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActiveUsersByMonthRow:
    year: int
    month: int
    active_count: int


@dataclass(frozen=True, slots=True)
class ActiveUsersByMonthDto:
    items: list[ActiveUsersByMonthRow]
