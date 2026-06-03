import csv

import uuid

from datetime import datetime, timezone

from io import StringIO



import pytest

from httpx import AsyncClient



from tests.conftest import _insert_test_user, scan_body





@pytest.mark.asyncio
async def test_scan_preview_returns_product_without_recording(
    client: AsyncClient, admin_token: str, sample_product: dict
):
    """Preview resolves QR to product name; does not create an attendance row."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    qr_resp = await client.get(f"/api/qr/token/{sample_product['id']}", headers=headers)
    assert qr_resp.status_code == 200
    qr_token = qr_resp.json()["qr_token"]

    list_before = await client.get("/api/attendance", headers=headers)
    assert list_before.status_code == 200
    count_before = len(list_before.json())

    preview = await client.post(
        "/api/attendance/scan/preview",
        json=scan_body(qr_token, sample_product),
        headers=headers,
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["product_id"] == sample_product["id"]
    assert body["product_name"] == sample_product["full_name"]
    assert body["product_type"] == sample_product["product_type"]

    list_after = await client.get("/api/attendance", headers=headers)
    assert len(list_after.json()) == count_before


@pytest.mark.asyncio

async def test_qr_issue_and_scan(client: AsyncClient, admin_token: str, sample_product: dict):

    """Happy path: admin issues QR for a product, then scans it to check in."""

    product_id = sample_product["id"]



    qr_resp = await client.get(

        f"/api/qr/token/{product_id}",

        headers={"Authorization": f"Bearer {admin_token}"},

    )

    assert qr_resp.status_code == 200

    qr_data = qr_resp.json()

    assert "qr_token" in qr_data

    assert qr_data["token_version"] == 1



    scan_resp = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_data["qr_token"], sample_product, device_id="kiosk-1"),

        headers={"Authorization": f"Bearer {admin_token}"},

    )

    assert scan_resp.status_code == 200

    event = scan_resp.json()

    assert event["event_type"] == "check_in"

    assert event["client_device_id"] == "kiosk-1"

    assert event["product_id"] == product_id

    assert event["attendance_status"] == "checked_in"





@pytest.mark.asyncio

async def test_same_token_toggles_in_then_out(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """The same QR scanned again should produce a check_out, no refresh needed."""

    product_id = sample_product["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}



    qr_token = (

        await client.get(f"/api/qr/token/{product_id}", headers=headers)

    ).json()["qr_token"]



    e1 = (

        await client.post(

            "/api/attendance/scan",

            json=scan_body(qr_token, sample_product),

            headers=headers,

        )

    ).json()

    assert e1["event_type"] == "check_in"

    assert e1["attendance_status"] == "checked_in"



    import asyncio

    await asyncio.sleep(3.2)



    e2 = (

        await client.post(

            "/api/attendance/scan",

            json=scan_body(qr_token, sample_product),

            headers=headers,

        )

    ).json()

    assert e2["event_type"] == "check_out"

    assert e2["attendance_status"] == "checked_out"

    assert e2["id"] != e1["id"]





@pytest.mark.asyncio

async def test_debounce_returns_existing_event(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """Rapid duplicate scans return the same event (kiosk double-tap protection)."""

    product_id = sample_product["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}



    qr_token = (

        await client.get(f"/api/qr/token/{product_id}", headers=headers)

    ).json()["qr_token"]



    scan1 = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product),

        headers=headers,

    )

    scan2 = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product),

        headers=headers,

    )

    assert scan1.status_code == 200

    assert scan2.status_code == 200

    assert scan1.json()["id"] == scan2.json()["id"]

    assert scan1.json()["event_type"] == "check_in"

    assert scan2.json()["event_type"] == "check_in"





@pytest.mark.asyncio

async def test_refresh_invalidates_old_token(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """After refresh, the previous QR token is rejected with 400."""

    product_id = sample_product["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}



    old_token = (

        await client.get(f"/api/qr/token/{product_id}", headers=headers)

    ).json()["qr_token"]



    refresh = await client.post(

        f"/api/qr/token/{product_id}/refresh", headers=headers

    )

    assert refresh.status_code == 200

    new_data = refresh.json()

    assert new_data["token_version"] == 2

    assert new_data["qr_token"] != old_token



    rejected = await client.post(

        "/api/attendance/scan",

        json=scan_body(old_token, sample_product),

        headers=headers,

    )

    assert rejected.status_code == 400



    accepted = await client.post(

        "/api/attendance/scan",

        json=scan_body(new_data["qr_token"], sample_product),

        headers=headers,

    )

    assert accepted.status_code == 200

    assert accepted.json()["event_type"] == "check_in"





@pytest.mark.asyncio

async def test_scan_with_explicit_event_type(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """Caller may pass event_type to force check_in or check_out."""

    product_id = sample_product["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}



    qr_token = (

        await client.get(f"/api/qr/token/{product_id}", headers=headers)

    ).json()["qr_token"]



    resp = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product, event_type="check_out"),

        headers=headers,

    )

    assert resp.status_code == 200

    body = resp.json()

    assert body["event_type"] == "check_out"

    assert body["attendance_status"] == "checked_out"



    import asyncio

    await asyncio.sleep(3.2)



    resp2 = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product, event_type="check_in"),

        headers=headers,

    )

    assert resp2.status_code == 200

    body2 = resp2.json()

    assert body2["event_type"] == "check_in"

    assert body2["attendance_status"] == "checked_in"





@pytest.mark.asyncio

async def test_unauthenticated_cannot_scan(client: AsyncClient):

    """Unauthenticated requests cannot use the scan endpoint."""

    resp = await client.post(

        "/api/attendance/scan",

        json={"qr_token": "fake"},

    )

    assert resp.status_code == 403





@pytest.mark.asyncio

async def test_invalid_qr_rejected(client: AsyncClient, admin_token: str):

    """Tampered token is rejected."""

    resp = await client.post(

        "/api/attendance/scan",

        json={"qr_token": "this.is.not.valid"},

        headers={"Authorization": f"Bearer {admin_token}"},

    )

    assert resp.status_code == 400





@pytest.mark.asyncio

async def test_manual_check_in_updates_status(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """A manual check_in correction should set the product's attendance_status."""

    product_id = sample_product["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}



    resp = await client.post(

        "/api/attendance/manual",

        json={"product_id": product_id, "event_type": "check_in"},

        headers=headers,

    )

    assert resp.status_code == 201

    assert resp.json()["attendance_status"] == "checked_in"



    product = (

        await client.get(f"/api/products/{product_id}", headers=headers)

    ).json()

    assert product["attendance_status"] == "checked_in"





@pytest.mark.asyncio

async def test_inactive_product_scan_rejected(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """Scanning an inactive product should be rejected."""

    product_id = sample_product["id"]

    headers = {"Authorization": f"Bearer {admin_token}"}



    qr_token = (

        await client.get(f"/api/qr/token/{product_id}", headers=headers)

    ).json()["qr_token"]



    await client.patch(

        f"/api/products/{product_id}",

        json={"is_active": False},

        headers=headers,

    )



    resp = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product),

        headers=headers,

    )

    assert resp.status_code == 400





@pytest.mark.asyncio

async def test_unauthenticated_cannot_list_attendance(client: AsyncClient):

    resp = await client.get("/api/attendance")

    assert resp.status_code == 403





@pytest.mark.asyncio

async def test_non_admin_cannot_scan_or_list(client: AsyncClient, admin_token: str, sample_product: dict):

    """Users without admin/superadmin role cannot scan or list attendance."""

    uname = f"staff_{uuid.uuid4().hex[:8]}"

    await _insert_test_user(

        username=uname,

        email=f"{uname}@test.com",

        password="staff123",

        role="staff",

    )

    login = await client.post("/api/auth/login", json={"username": uname, "password": "staff123"})

    assert login.status_code == 200

    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}



    qr_resp = await client.get(

        f"/api/qr/token/{sample_product['id']}",

        headers={"Authorization": f"Bearer {admin_token}"},

    )

    qr_token = qr_resp.json()["qr_token"]



    scan_resp = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product),

        headers=headers,

    )

    assert scan_resp.status_code == 403



    list_resp = await client.get("/api/attendance", headers=headers)

    assert list_resp.status_code == 403





@pytest.mark.asyncio

async def test_export_csv_quotes_commas_in_fields(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """CSV export must quote fields that contain commas."""

    headers = {"Authorization": f"Bearer {admin_token}"}

    product_id = sample_product["id"]



    patch = await client.patch(

        f"/api/products/{product_id}",

        json={"full_name": "Tanaka, Taro"},

        headers=headers,

    )

    assert patch.status_code == 200



    qr_resp = await client.get(f"/api/qr/token/{product_id}", headers=headers)

    assert qr_resp.status_code == 200

    qr_token = qr_resp.json()["qr_token"]



    scan = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product),

        headers=headers,

    )

    assert scan.status_code == 200



    export = await client.get(

        "/api/attendance/export/csv",

        params={

            "date_from": datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat(),

            "date_to": datetime(2099, 12, 31, tzinfo=timezone.utc).isoformat(),

        },

        headers=headers,

    )

    assert export.status_code == 200

    rows = list(csv.reader(StringIO(export.text)))

    assert rows[0][3] == "product_name"

    data_rows = [r for r in rows[1:] if r and r[1] == product_id]

    assert len(data_rows) >= 1

    assert data_rows[-1][3] == "Tanaka, Taro"





@pytest.mark.asyncio

async def test_scan_records_location_on_product(

    client: AsyncClient, admin_token: str, sample_product: dict, sample_location: dict

):

    headers = {"Authorization": f"Bearer {admin_token}"}

    product_id = sample_product["id"]



    qr_resp = await client.get(f"/api/qr/token/{product_id}", headers=headers)

    qr_token = qr_resp.json()["qr_token"]



    scan = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product, location_id=sample_location["id"]),

        headers=headers,

    )

    assert scan.status_code == 200

    assert scan.json()["location"] == sample_location["name_en"]



    product = await client.get(f"/api/products/{product_id}", headers=headers)

    assert product.status_code == 200

    body = product.json()

    assert body["last_event_location"] == sample_location["name_en"]

    assert body["last_event_at"] is not None





@pytest.mark.asyncio

async def test_scan_rejects_location_not_in_whitelist(

    client: AsyncClient,

    admin_token: str,

    sample_product: dict,

    sample_location_b: dict,

):

    headers = {"Authorization": f"Bearer {admin_token}"}

    qr_token = (

        await client.get(f"/api/qr/token/{sample_product['id']}", headers=headers)

    ).json()["qr_token"]



    resp = await client.post(

        "/api/attendance/scan",

        json=scan_body(qr_token, sample_product, location_id=sample_location_b["id"]),

        headers=headers,

    )

    assert resp.status_code == 403
    body = resp.json()["detail"]
    assert body["code"] == "location_not_allowed"
    assert len(body["allowed_locations"]) >= 1
    allowed_ids = {loc["id"] for loc in body["allowed_locations"]}
    assert str(sample_product["scan_location_ids"][0]) in allowed_ids
    assert str(sample_location_b["id"]) not in allowed_ids


@pytest.mark.asyncio
async def test_scan_preview_rejects_location_with_allowed_list(
    client: AsyncClient,
    admin_token: str,
    sample_product: dict,
    sample_location_b: dict,
):
    headers = {"Authorization": f"Bearer {admin_token}"}
    qr_token = (
        await client.get(f"/api/qr/token/{sample_product['id']}", headers=headers)
    ).json()["qr_token"]
    resp = await client.post(
        "/api/attendance/scan/preview",
        json=scan_body(qr_token, sample_product, location_id=sample_location_b["id"]),
        headers=headers,
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["product_name"] == sample_product["full_name"]
    assert len(detail["allowed_locations"]) >= 1


@pytest.mark.asyncio

async def test_scan_requires_location_id(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    headers = {"Authorization": f"Bearer {admin_token}"}

    qr_token = (

        await client.get(f"/api/qr/token/{sample_product['id']}", headers=headers)

    ).json()["qr_token"]



    resp = await client.post(

        "/api/attendance/scan",

        json={"qr_token": qr_token},

        headers=headers,

    )

    assert resp.status_code == 400





@pytest.mark.asyncio

async def test_attendance_day_stats_aggregates_all_events(

    client: AsyncClient, admin_token: str, sample_product: dict

):

    """Stats endpoint counts all events, not just the first page."""

    headers = {"Authorization": f"Bearer {admin_token}"}

    product_id = sample_product["id"]



    for event_type in ("check_in", "check_out", "check_in"):

        resp = await client.post(

            "/api/attendance/manual",

            json={"product_id": product_id, "event_type": event_type},

            headers=headers,

        )

        assert resp.status_code == 201



    stats = await client.get("/api/attendance/stats", headers=headers)

    assert stats.status_code == 200

    body = stats.json()

    assert body["total"] >= 3

    assert body["check_ins_student"] >= 2

    assert body["check_outs_student"] >= 1



    list_resp = await client.get(

        "/api/attendance",

        params={"page_size": 2},

        headers=headers,

    )

    assert list_resp.status_code == 200

    assert int(list_resp.headers["X-Total-Count"]) >= 3

    assert len(list_resp.json()) == 2





@pytest.mark.asyncio

async def test_unauthenticated_cannot_get_attendance_stats(client: AsyncClient):

    resp = await client.get("/api/attendance/stats")

    assert resp.status_code == 403


