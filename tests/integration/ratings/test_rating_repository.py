from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription
from app.infrastructure.db.mappings.user import UserModel
from app.infrastructure.db.mappings.resource import ResourceModel
from app.infrastructure.db.mappings.resource_type import ResourceTypeModel
from app.infrastructure.db.mappings.booking import BookingModel
from app.infrastructure.repositories.rating_repository import (
    SQLAlchemyRatingRepository,
)


pytestmark = pytest.mark.asyncio


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _score(v: int = 5) -> RatingScore:
    return RatingScore.create(v).value


async def _seed_booking_for_rating(db_session) -> tuple[UUID, UUID, UUID]:
    """Insert a user, resource_type, resource, and APPROVED booking so
    a rating can be inserted with valid FKs. Returns (booking_id,
    resource_id, customer_id)."""
    rt = ResourceTypeModel(
        id=str(uuid4()), slug="football-field", name="Football Field",
        description="", attribute_schema=[], is_active=True,
        created_at=_now(), updated_at=_now(),
    )
    owner = UserModel(
        id=str(uuid4()), email="o@example.com", full_name="Owner",
        password_hash="x", role="owner", is_active=True,
        public_slug="owner", phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    customer = UserModel(
        id=str(uuid4()), email="c@example.com", full_name="Customer",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    res = ResourceModel(
        id=str(uuid4()), owner_id=owner.id, resource_type_id=rt.id,
        slug="campo", name="Campo", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours={"monday": [{"start": "06:00", "end": "22:00"}]},
        pricing_rules=[], custom_attributes=[], base_attributes={},
        is_published=True, deleted_at=None,
        created_at=_now(), updated_at=_now(),
    )
    booking = BookingModel(
        id=str(uuid4()), resource_id=res.id, customer_id=customer.id,
        slot_start_at=_now() - timedelta(days=1, hours=1),
        slot_end_at=_now() - timedelta(days=1),
        status="APPROVED",
        customer_note=None, total_price_cents=8000,
        status_history=[],
        created_at=_now() - timedelta(days=2), updated_at=_now() - timedelta(days=2),
    )
    db_session.add_all([rt, owner, customer, res, booking])
    await db_session.flush()
    return UUID(booking.id), UUID(res.id), UUID(customer.id)


async def test_add_and_get_round_trip(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    note = ShortDescription.create("ótimo lugar").value
    rating = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=note, now=_now(),
    )
    add_r = await repo.add(rating)
    assert add_r.is_success

    fetched = (await repo.get_by_id(rating.id)).value
    assert fetched is not None
    assert fetched.id == rating.id
    assert fetched.score.value == 5
    assert fetched.comment is not None
    assert fetched.comment.value == "ótimo lugar"

    by_booking = (await repo.get_by_booking_id(booking_id)).value
    assert by_booking is not None
    assert by_booking.id == rating.id


async def test_unique_booking_id_rejected(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    a = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=None, now=_now(),
    )
    b = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(3), comment=None, now=_now(),
    )
    await repo.add(a)
    second = await repo.add(b)
    assert second.is_failure
    assert second.error == "RatingAlreadyExists"
    assert second.status_code == 409


async def test_list_with_comment_excludes_null_comments(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    no_comment = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=None, now=_now(),
    )
    await repo.add(no_comment)

    items = (await repo.list_with_comment_for_resource(
        resource_id, page=1, page_size=10,
    )).value
    assert items == []


async def test_list_by_customer_orders_desc(db_session):
    """Insert two ratings for the same customer across different bookings;
    verify newest-first ordering."""
    rt = ResourceTypeModel(
        id=str(uuid4()), slug="court", name="Court",
        description="", attribute_schema=[], is_active=True,
        created_at=_now(), updated_at=_now(),
    )
    owner = UserModel(
        id=str(uuid4()), email="o2@example.com", full_name="Owner2",
        password_hash="x", role="owner", is_active=True,
        public_slug="owner2", phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    customer = UserModel(
        id=str(uuid4()), email="c2@example.com", full_name="Customer2",
        password_hash="x", role="customer", is_active=True,
        public_slug=None, phone_number=None,
        created_at=_now(), updated_at=_now(),
    )
    res = ResourceModel(
        id=str(uuid4()), owner_id=owner.id, resource_type_id=rt.id,
        slug="court-1", name="Court 1", description="",
        city="SP", region="SP", timezone="America/Sao_Paulo",
        slot_duration_minutes=60, base_price_cents=8000,
        customer_cancellation_cutoff_hours=24,
        operating_hours={"monday": [{"start": "06:00", "end": "22:00"}]},
        pricing_rules=[], custom_attributes=[], base_attributes={},
        is_published=True, deleted_at=None,
        created_at=_now(), updated_at=_now(),
    )
    db_session.add_all([rt, owner, customer, res])
    await db_session.flush()
    customer_id = UUID(customer.id)
    resource_id = UUID(res.id)

    # Two distinct bookings + two distinct ratings.
    bookings_pairs = []
    for i in range(2):
        b = BookingModel(
            id=str(uuid4()), resource_id=res.id, customer_id=customer.id,
            slot_start_at=_now() - timedelta(days=2 * (i + 1), hours=1),
            slot_end_at=_now() - timedelta(days=2 * (i + 1)),
            status="APPROVED",
            customer_note=None, total_price_cents=8000,
            status_history=[],
            created_at=_now() - timedelta(days=2 * (i + 1) + 1),
            updated_at=_now() - timedelta(days=2 * (i + 1) + 1),
        )
        db_session.add(b)
        bookings_pairs.append((UUID(b.id), b))
    await db_session.flush()

    repo = SQLAlchemyRatingRepository(db_session)
    older = Rating.create(
        booking_id=bookings_pairs[0][0],
        resource_id=resource_id, customer_id=customer_id,
        score=_score(4), comment=None,
        now=_now() - timedelta(days=3),
    )
    newer = Rating.create(
        booking_id=bookings_pairs[1][0],
        resource_id=resource_id, customer_id=customer_id,
        score=_score(5), comment=None, now=_now(),
    )
    await repo.add(older)
    await repo.add(newer)

    items = (await repo.list_by_customer(
        customer_id, page=1, page_size=10,
    )).value
    assert [r.id for r in items] == [newer.id, older.id]


async def test_get_aggregates_for_resources_full_coverage(db_session):
    booking_id, resource_id, customer_id = await _seed_booking_for_rating(db_session)
    repo = SQLAlchemyRatingRepository(db_session)
    rating = Rating.create(
        booking_id=booking_id, resource_id=resource_id, customer_id=customer_id,
        score=_score(4), comment=None, now=_now(),
    )
    await repo.add(rating)

    other_resource_id = uuid4()  # never seeded; should appear with (None, 0)
    aggs = (await repo.get_aggregates_for_resources(
        [resource_id, other_resource_id],
    )).value
    assert resource_id in aggs
    assert other_resource_id in aggs
    assert aggs[resource_id].count == 1
    assert aggs[resource_id].avg_score == Decimal("4.0")
    assert aggs[other_resource_id].count == 0
    assert aggs[other_resource_id].avg_score is None
