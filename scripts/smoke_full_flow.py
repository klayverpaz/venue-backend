"""End-to-end smoke against a running Docker stack.

Walks the public/owner/customer/admin endpoints, populating the DB with a
realistic dataset and asserting each step's status code + key payload bits.

Pre-reqs:
    docker compose up -d --build
    docker compose exec app python -m scripts.bootstrap_admin

Usage:
    .venv/bin/python -m scripts.smoke_full_flow [--base-url http://localhost:8000]

Re-runnable: each user/resource gets a timestamp suffix, so the script can be
run repeatedly against the same DB without dedup conflicts.
"""
from __future__ import annotations
import argparse
import asyncio
import datetime as dt
import json
import sys
import time
import uuid

import httpx


ADMIN_EMAIL = "admin@venue.app"
ADMIN_PASSWORD = "AdminDev!2026"


class SmokeError(RuntimeError):
    pass


def _expect(resp: httpx.Response, expected: int | tuple[int, ...]) -> None:
    expected_tuple = (expected,) if isinstance(expected, int) else expected
    if resp.status_code not in expected_tuple:
        raise SmokeError(
            f"{resp.request.method} {resp.request.url} -> {resp.status_code} "
            f"(expected {expected_tuple}); body={resp.text[:1000]}"
        )


def _print_step(n: int, title: str) -> None:
    print(f"\n=== {n:>2}. {title} ===")


async def _login(client: httpx.AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/v1/auth/login", json={"email": email, "password": password})
    _expect(r, 200)
    return r.json()


async def _register(
    client: httpx.AsyncClient, *, email: str, password: str, role: str, full_name: str, phone: str | None = None
) -> dict:
    payload = {"email": email, "password": password, "role": role, "full_name": full_name, "phone": phone}
    r = await client.post("/v1/auth/register", json=payload)
    _expect(r, (200, 201))
    return r.json()


async def run(base_url: str) -> None:
    suffix = str(int(time.time()))
    owner_email = f"owner-{suffix}@venue.app"
    customer_email = f"customer-{suffix}@venue.app"
    rt_slug = f"football-field-{suffix}"
    resource_slug = f"campo-principal-{suffix}"
    common_password = "SmokeTest!2026"

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # 1) Admin login
        _print_step(1, "Admin login")
        admin_pair = await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        admin_token = admin_pair["access_token"]
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        print(f"   admin id={admin_pair['user']['id']} role={admin_pair['user']['role']}")

        # 2) Create ResourceType (Football Field)
        _print_step(2, "POST /v1/admin/resource-types")
        rt_payload = {
            "slug": rt_slug,
            "name": "Football Field",
            "description": "Outdoor 11-vs-11 grass pitch.",
            "attribute_schema": [
                {"key": "surface", "label": "Surface", "data_type": "enum",
                 "required": True, "enum_values": ["grass", "synthetic"]},
                {"key": "lighting", "label": "Has lighting", "data_type": "bool", "required": False},
                {"key": "capacity", "label": "Capacity", "data_type": "int", "required": False},
            ],
            "is_active": True,
        }
        r = await client.post("/v1/admin/resource-types", json=rt_payload, headers=admin_h)
        _expect(r, 201)
        rt = r.json()
        rt_id = rt["id"]
        print(f"   rt_id={rt_id} slug={rt['slug']}")

        # 3) Catalog public listing
        _print_step(3, "GET /v1/catalog/resource-types (public)")
        r = await client.get("/v1/catalog/resource-types")
        _expect(r, 200)
        slugs = [item["slug"] for item in r.json()["items"]]
        assert rt_slug in slugs, f"new RT not in public catalog; got {slugs}"
        print(f"   {len(slugs)} active RTs in catalog")

        # 4) Register owner + login
        _print_step(4, "Register + login owner")
        await _register(
            client, email=owner_email, password=common_password,
            role="owner", full_name=f"Owner Smoke {suffix}",
        )
        owner_pair = await _login(client, owner_email, common_password)
        owner_token = owner_pair["access_token"]
        owner_h = {"Authorization": f"Bearer {owner_token}"}
        owner_id = owner_pair["user"]["id"]
        owner_slug = owner_pair["user"]["public_slug"]
        print(f"   owner_id={owner_id} public_slug={owner_slug}")

        # 5) Register customer + login
        _print_step(5, "Register + login customer")
        await _register(
            client, email=customer_email, password=common_password,
            role="customer", full_name=f"Customer Smoke {suffix}",
        )
        customer_pair = await _login(client, customer_email, common_password)
        customer_token = customer_pair["access_token"]
        customer_h = {"Authorization": f"Bearer {customer_token}"}
        customer_id = customer_pair["user"]["id"]
        print(f"   customer_id={customer_id}")

        # 6) Owner subscription (should be TRIALING / operational)
        _print_step(6, "GET /v1/me/subscription (owner)")
        r = await client.get("/v1/me/subscription", headers=owner_h)
        _expect(r, 200)
        sub = r.json()
        assert sub["is_operational"] is True, f"new owner sub not operational: {sub}"
        print(f"   status={sub['status']} operational={sub['is_operational']} trial_ends_at={sub['trial_ends_at']}")

        # 7) Create Resource (UTC, 08-22 every day, slot=60min)
        _print_step(7, "POST /v1/me/resources (owner)")
        weekly = {day: [{"start": "08:00", "end": "22:00"}]
                  for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}
        resource_payload = {
            "resource_type_id": rt_id,
            "slug": resource_slug,
            "name": f"Campo Principal {suffix}",
            "description": "Campo de futebol 11x11, gramado natural.",
            "city": "São Paulo",
            "region": "SP",
            "timezone": "UTC",
            "slot_duration_minutes": 60,
            "operating_hours": weekly,
            "base_price_cents": 12000,
            "customer_cancellation_cutoff_hours": 6,
            "base_attributes": {"surface": "grass", "lighting": True, "capacity": 22},
            "pricing_rules": [],
            "custom_attributes": [
                {"key": "amenities", "label": "Amenities", "value": "Vestiário, estacionamento"},
            ],
        }
        r = await client.post("/v1/me/resources", json=resource_payload, headers=owner_h)
        _expect(r, 201)
        resource = r.json()
        resource_id = resource["id"]
        print(f"   resource_id={resource_id} is_published={resource['is_published']}")

        # 8) Public listing should NOT include unpublished
        _print_step(8, "GET /v1/resources (public, before publish)")
        r = await client.get("/v1/resources")
        _expect(r, 200)
        ids = [item["id"] for item in r.json()["items"]]
        assert resource_id not in ids, "unpublished resource leaked to public listing"
        print(f"   public listing has {len(ids)} resources (unpublished resource correctly hidden)")

        # 9) Publish
        _print_step(9, "POST /v1/me/resources/{id}/publish")
        r = await client.post(f"/v1/me/resources/{resource_id}/publish", headers=owner_h)
        _expect(r, 200)
        assert r.json()["is_published"] is True
        print("   resource published")

        # 10) Public listing now includes it
        _print_step(10, "GET /v1/resources (public, after publish)")
        r = await client.get("/v1/resources")
        _expect(r, 200)
        items = {item["id"]: item for item in r.json()["items"]}
        assert resource_id in items, "published resource missing from listing"
        listing_item = items[resource_id]
        assert listing_item["rating_avg"] is None, f"new resource rating_avg should be null; got {listing_item['rating_avg']}"
        assert listing_item["rating_count"] == 0
        print(f"   resource visible; rating_avg={listing_item['rating_avg']} rating_count={listing_item['rating_count']}")

        # 11) Public detail by slug
        _print_step(11, "GET /v1/owners/{owner_slug}/resources/{resource_slug}")
        r = await client.get(f"/v1/owners/{owner_slug}/resources/{resource_slug}")
        _expect(r, 200)
        assert r.json()["id"] == resource_id
        print("   public detail OK")

        # 12) Customer requests booking — slot tomorrow 14:00 UTC
        _print_step(12, "POST /v1/me/bookings (customer)")
        slot_start = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        slot_end = slot_start + dt.timedelta(hours=1)
        booking_payload = {
            "resource_id": resource_id,
            "slot_start_at": slot_start.isoformat(),
            "slot_end_at": slot_end.isoformat(),
            "customer_note": "Pelada da firma",
        }
        r = await client.post("/v1/me/bookings", json=booking_payload, headers=customer_h)
        _expect(r, 201)
        booking = r.json()
        booking_id = booking["id"]
        assert booking["status"] == "PENDING"
        assert booking["total_price_cents"] == 12000
        print(f"   booking_id={booking_id} status={booking['status']} price={booking['total_price_cents']}")

        # 13) Customer lists own bookings
        _print_step(13, "GET /v1/me/bookings (customer)")
        r = await client.get("/v1/me/bookings", headers=customer_h)
        _expect(r, 200)
        ids = [b["id"] for b in r.json()["items"]]
        assert booking_id in ids
        print(f"   {len(ids)} booking(s) listed")

        # 14) Owner sees the booking on resource
        _print_step(14, "GET /v1/me/resources/{id}/bookings (owner)")
        r = await client.get(f"/v1/me/resources/{resource_id}/bookings", headers=owner_h)
        _expect(r, 200)
        ids = [b["id"] for b in r.json()["items"]]
        assert booking_id in ids
        print(f"   {len(ids)} booking(s) on resource")

        # 15) Owner approves
        _print_step(15, "POST /v1/me/bookings/{id}/approve (owner)")
        r = await client.post(f"/v1/me/bookings/{booking_id}/approve", headers=owner_h)
        _expect(r, 200)
        assert r.json()["status"] == "APPROVED"
        print("   approved")

        # 16) Owner agenda
        _print_step(16, "GET /v1/me/resources/{id}/agenda (owner)")
        agenda_from = slot_start.isoformat()
        agenda_to = (slot_start + dt.timedelta(days=2)).isoformat()
        r = await client.get(
            f"/v1/me/resources/{resource_id}/agenda",
            params={"from": agenda_from, "to": agenda_to},
            headers=owner_h,
        )
        _expect(r, 200)
        slots = r.json().get("slots", [])
        booked = [s for s in slots if s.get("booking_id") == booking_id]
        assert booked, f"approved booking missing from agenda; first 3 slots={slots[:3]}"
        print(f"   {len(slots)} agenda slots; approved slot found")

        # 17) Public agenda
        _print_step(17, "GET /v1/resources/{owner_slug}/{resource_slug}/agenda (public)")
        r = await client.get(
            f"/v1/resources/{owner_slug}/{resource_slug}/agenda",
            params={"from": agenda_from, "to": agenda_to},
        )
        _expect(r, 200)
        print(f"   {len(r.json().get('slots', []))} public agenda slots")

        # 18) Owner notifications include BOOKING_REQUESTED + BOOKING_APPROVED
        _print_step(18, "GET /v1/me/notifications (owner)")
        r = await client.get("/v1/me/notifications", headers=owner_h)
        _expect(r, 200)
        kinds = [n["kind"] for n in r.json()["items"]]
        assert "BOOKING_REQUESTED" in kinds, f"BOOKING_REQUESTED missing; kinds={kinds}"
        assert "BOOKING_APPROVED" not in kinds, f"BOOKING_APPROVED should go to customer, not owner; kinds={kinds}"
        print(f"   owner notifications kinds={kinds}")

        # 19) Customer notifications include BOOKING_APPROVED
        _print_step(19, "GET /v1/me/notifications (customer)")
        r = await client.get("/v1/me/notifications", headers=customer_h)
        _expect(r, 200)
        kinds = [n["kind"] for n in r.json()["items"]]
        assert "BOOKING_APPROVED" in kinds, f"BOOKING_APPROVED missing; kinds={kinds}"
        print(f"   customer notifications kinds={kinds}")

        # 20) Admin lists subscriptions
        _print_step(20, "GET /v1/admin/subscriptions (admin)")
        r = await client.get("/v1/admin/subscriptions", headers=admin_h)
        _expect(r, 200)
        owner_ids = [s["owner_id"] for s in r.json()["items"]]
        assert owner_id in owner_ids
        print(f"   {len(owner_ids)} subscription(s) listed")

        # 21) Admin lists users
        _print_step(21, "GET /v1/admin/users (admin)")
        r = await client.get("/v1/admin/users", headers=admin_h)
        _expect(r, 200)
        emails = [u["email"] for u in r.json()["items"]]
        assert owner_email in emails and customer_email in emails
        print(f"   {len(emails)} user(s) listed")

        # 22) /v1/me round-trip
        _print_step(22, "GET /v1/me (each role)")
        for label, hdr in [("admin", admin_h), ("owner", owner_h), ("customer", customer_h)]:
            r = await client.get("/v1/me", headers=hdr)
            _expect(r, 200)
            print(f"   {label}: {r.json()['email']} role={r.json()['role']}")

        # 23) Public owner page
        _print_step(23, "GET /v1/owners/{owner_slug} (public)")
        r = await client.get(f"/v1/owners/{owner_slug}")
        _expect(r, 200)
        body = r.json()
        assert any(res["id"] == resource_id for res in body.get("resources", [])), \
            f"published resource missing from owner page: {body}"
        print(f"   owner page lists {len(body.get('resources', []))} resource(s)")

        print("\nSMOKE OK ✅")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8000")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        asyncio.run(run(args.base_url))
    except SmokeError as e:
        print(f"\nSMOKE FAILED ❌\n{e}", file=sys.stderr)
        sys.exit(1)
