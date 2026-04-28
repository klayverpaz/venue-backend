from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.ratings.rating import Rating
from app.domain.shared.value_objects.rating_score import RatingScore
from app.domain.shared.value_objects.short_description import ShortDescription


def _now() -> datetime:
    return datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


def _score(v: int = 5) -> RatingScore:
    return RatingScore.create(v).value


def test_create_sets_initial_state():
    bid, rid, cid = uuid4(), uuid4(), uuid4()
    r = Rating.create(
        booking_id=bid, resource_id=rid, customer_id=cid,
        score=_score(5), comment=None, now=_now(),
    )
    assert r.booking_id == bid
    assert r.resource_id == rid
    assert r.customer_id == cid
    assert r.score.value == 5
    assert r.comment is None
    assert r.created_at == _now()
    assert r.updated_at == _now()


def test_create_with_comment():
    note = ShortDescription.create("Excelente").value
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(4), comment=note, now=_now(),
    )
    assert r.comment is note


def test_create_generates_unique_ids():
    a = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(), comment=None, now=_now(),
    )
    b = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(), comment=None, now=_now(),
    )
    assert a.id != b.id


def test_update_text_changes_score_and_comment():
    note_old = ShortDescription.create("primeiro").value
    note_new = ShortDescription.create("segundo").value
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(3), comment=note_old, now=_now(),
    )
    r.update_text(score=_score(5), comment=note_new, now=_now())
    assert r.score.value == 5
    assert r.comment is note_new


def test_update_text_can_clear_comment():
    note = ShortDescription.create("será apagado").value
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(4), comment=note, now=_now(),
    )
    r.update_text(score=_score(4), comment=None, now=_now())
    assert r.comment is None


def test_update_text_bumps_updated_at():
    from datetime import timedelta
    r = Rating.create(
        booking_id=uuid4(), resource_id=uuid4(), customer_id=uuid4(),
        score=_score(5), comment=None, now=_now(),
    )
    later = _now() + timedelta(days=1)
    r.update_text(score=_score(4), comment=None, now=later)
    assert r.updated_at == later
    assert r.created_at == _now()
