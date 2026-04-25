from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.mappings.user import UserModel
from app.use_cases.reports.queries.active_users_by_month import (
    ActiveUsersByMonthHandler, ActiveUsersByMonthQuery,
)


async def _seed_user(
    s: AsyncSession,
    *,
    email: str,
    created_at: datetime,
    is_active: bool = True,
) -> None:
    s.add(UserModel(
        id=str(uuid4()),
        name="seed",
        email=email,
        phone="+5521996949389",
        credit_score=0.0,
        balance=0.0,
        is_active=is_active,
        created_at=created_at,
        updated_at=created_at,
    ))
    await s.commit()


@pytest.mark.asyncio
async def test_groups_active_users_by_year_and_month(db_session: AsyncSession):
    # Seed in DESCENDING date order so a missing ORDER BY would surface as
    # rows out-of-order (insertion order ≠ contract order).
    await _seed_user(db_session, email="c@x.com", created_at=datetime(2026, 2, 3, tzinfo=timezone.utc))
    await _seed_user(db_session, email="b@x.com", created_at=datetime(2026, 1, 20, tzinfo=timezone.utc))
    await _seed_user(db_session, email="a@x.com", created_at=datetime(2026, 1, 5, tzinfo=timezone.utc))

    handler = ActiveUsersByMonthHandler(db_session)
    result = await handler.handle(ActiveUsersByMonthQuery())

    assert result.is_success
    rows = [(r.year, r.month, r.active_count) for r in result.value.items]
    assert (2026, 1, 2) in rows
    assert (2026, 2, 1) in rows
    # ORDER BY year, month is part of the contract — assert ascending order.
    # Load-bearing because seed order above is descending.
    assert rows == sorted(rows)


@pytest.mark.asyncio
async def test_excludes_inactive_users(db_session: AsyncSession):
    await _seed_user(db_session, email="a@x.com", created_at=datetime(2026, 3, 5, tzinfo=timezone.utc), is_active=True)
    await _seed_user(db_session, email="b@x.com", created_at=datetime(2026, 3, 6, tzinfo=timezone.utc), is_active=False)

    handler = ActiveUsersByMonthHandler(db_session)
    result = await handler.handle(ActiveUsersByMonthQuery())

    rows = [(r.year, r.month, r.active_count) for r in result.value.items]
    assert (2026, 3, 1) in rows
    # The inactive user must NOT have inflated the active count
    assert (2026, 3, 2) not in rows


@pytest.mark.asyncio
async def test_returns_empty_dto_when_no_users(db_session: AsyncSession):
    handler = ActiveUsersByMonthHandler(db_session)
    result = await handler.handle(ActiveUsersByMonthQuery())
    assert result.is_success
    assert result.value.items == []


@pytest.mark.asyncio
async def test_distinguishes_same_month_across_years(db_session: AsyncSession):
    await _seed_user(db_session, email="2025@x.com", created_at=datetime(2025, 1, 10, tzinfo=timezone.utc))
    await _seed_user(db_session, email="2026@x.com", created_at=datetime(2026, 1, 10, tzinfo=timezone.utc))

    handler = ActiveUsersByMonthHandler(db_session)
    result = await handler.handle(ActiveUsersByMonthQuery())

    rows = [(r.year, r.month, r.active_count) for r in result.value.items]
    assert (2025, 1, 1) in rows
    assert (2026, 1, 1) in rows
    assert len(rows) == 2
