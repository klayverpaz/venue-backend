from __future__ import annotations
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.api.v1.me_resources.schemas import ResourceResponse
from app.api.v1.public_resources.schemas import OwnerPublicPageResponse


def _minimal_resource_response(*, rating_avg=None, rating_count=0):
    """Build the smallest ResourceResponse instance that satisfies the model.
    Only rating_avg + rating_count matter for this test; other fields are
    filled with placeholders."""
    return ResourceResponse(
        id=uuid4(),
        owner_id=uuid4(),
        owner_slug="o",
        resource_type_id=uuid4(),
        resource_type_slug="rt",
        slug="r",
        name="r",
        description="",
        city="",
        region="",
        timezone="UTC",
        slot_duration_minutes=60,
        base_price_cents=0,
        customer_cancellation_cutoff_hours=24,
        operating_hours={
            "monday": [], "tuesday": [], "wednesday": [], "thursday": [],
            "friday": [], "saturday": [], "sunday": [],
        },
        pricing_rules=[],
        custom_attributes=[],
        base_attributes={},
        is_published=False,
        deleted_at=None,
        created_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 28, tzinfo=timezone.utc),
        rating_avg=rating_avg,
        rating_count=rating_count,
    )


def test_rating_avg_serializes_as_number_not_string():
    resp = _minimal_resource_response(
        rating_avg=Decimal("4.3"), rating_count=10,
    )
    data = json.loads(resp.model_dump_json())
    assert data["rating_avg"] == 4.3
    assert isinstance(data["rating_avg"], (int, float))
    assert data["rating_count"] == 10


def test_rating_avg_none_serializes_as_json_null():
    resp = _minimal_resource_response(rating_avg=None, rating_count=0)
    data = json.loads(resp.model_dump_json())
    assert data["rating_avg"] is None
    assert data["rating_count"] == 0


def test_owner_rating_avg_serializes_as_number_not_string():
    """OwnerPublicPageResponse.owner_rating_avg must also serialize as float."""
    page = OwnerPublicPageResponse(
        owner_id=uuid4(),
        owner_slug="o",
        full_name="Owner",
        resources=[],
        owner_rating_avg=Decimal("3.7"),
        owner_rating_count=5,
    )
    data = json.loads(page.model_dump_json())
    assert data["owner_rating_avg"] == 3.7
    assert isinstance(data["owner_rating_avg"], (int, float))


def test_owner_rating_avg_none_serializes_as_json_null():
    page = OwnerPublicPageResponse(
        owner_id=uuid4(),
        owner_slug="o",
        full_name="Owner",
        resources=[],
        owner_rating_avg=None,
        owner_rating_count=0,
    )
    data = json.loads(page.model_dump_json())
    assert data["owner_rating_avg"] is None
