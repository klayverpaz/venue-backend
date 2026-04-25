from __future__ import annotations
from app.domain.shared.value_objects.rating_score import RatingScore


def test_rating_score_accepts_1_to_5():
    for n in [1, 2, 3, 4, 5]:
        r = RatingScore.create(n)
        assert r.is_success, f"failed for {n}"
        assert r.value.value == n


def test_rating_score_rejects_zero():
    r = RatingScore.create(0)
    assert r.is_failure
    assert r.error == RatingScore.RATING_SCORE_OUT_OF_RANGE


def test_rating_score_rejects_six():
    r = RatingScore.create(6)
    assert r.is_failure
    assert r.error == RatingScore.RATING_SCORE_OUT_OF_RANGE


def test_rating_score_rejects_negative():
    r = RatingScore.create(-1)
    assert r.is_failure
    assert r.error == RatingScore.RATING_SCORE_OUT_OF_RANGE


def test_rating_score_rejects_non_int():
    for bad in [None, 1.5, "5", True]:
        r = RatingScore.create(bad)
        assert r.is_failure, f"expected failure for {bad!r}"
        assert r.error == RatingScore.RATING_SCORE_INVALID_TYPE
