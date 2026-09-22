import uuid

import pytest
from httpx import AsyncClient

from tests.test_tuition_invoices import _auth, _create_sku, _create_spu, _enroll


async def _issue(client: AsyncClient, token: str, invoice_id: str) -> dict:
    resp = await client.patch(
        f"/api/tuition-invoices/{invoice_id}",
        json={"status": "issued"},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _issued_monthly(
    client: AsyncClient,
    token: str,
    unit_id: str,
    year: int,
    month: int,
) -> dict:
    listed = await client.get(
        f"/api/tuition-invoices?year={year}&month={month}",
        headers=_auth(token),
    )
    invoice = next(row for row in listed.json() if row["unit_id"] == unit_id)
    return await _issue(client, token, invoice["id"])


async def _manual_invoice(
    client: AsyncClient,
    token: str,
    location_id: str,
    *,
    unit_id: str | None = None,
    name: str | None = None,
    date: str = "2026-09-02",
    fee: float = 100,
) -> dict:
    payload: dict = {
        "date": date,
        "location_id": location_id,
        "lines": [{"month": "Sept-26", "course": "私補", "fee": fee, "qty": 1}],
    }
    if unit_id:
        payload["unit_id"] = unit_id
    else:
        payload["manual_student_name"] = name
    resp = await client.post("/api/tuition-invoices/manual", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _enroll_two_months(client: AsyncClient, token: str, unit_id: str) -> None:
    spu = await _create_spu(client, token)
    sku = await _create_sku(client, token, spu["id"])
    await _enroll(
        client,
        token,
        unit_id,
        sku["id"],
        start_date="2026-06-01",
        end_date="2026-07-31",
    )
    for month in (6, 7):
        resp = await client.post(
            f"/api/tuition-invoices/generate?year=2026&month={month}",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_create_receipt_pays_multiple_invoices_for_one_student(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    await _enroll_two_months(client, admin_token, sample_unit["id"])
    june = await _issued_monthly(client, admin_token, sample_unit["id"], 2026, 6)
    july = await _issued_monthly(client, admin_token, sample_unit["id"], 2026, 7)

    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "FPS",
            "receipt_date": "2026-09-02",
            "invoice_ids": [june["id"], july["id"]],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    receipt = resp.json()
    assert receipt["receipt_no"] == "R260902"
    assert receipt["status"] == "posted"
    assert receipt["paid_by"] == "FPS"
    assert float(receipt["amount"]) == 1600
    assert {row["invoice_id"] for row in receipt["invoices"]} == {june["id"], july["id"]}
    print_courses = {line["course"] for line in receipt["print_lines"]}
    assert print_courses

    for invoice_id in (june["id"], july["id"]):
        fetched = await client.get(f"/api/tuition-invoices/{invoice_id}", headers=_auth(admin_token))
        assert fetched.json()["status"] == "paid"
        assert fetched.json()["receipt_no"] == "R260902"


@pytest.mark.asyncio
async def test_create_receipt_rejects_invoices_from_another_student(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    other = await client.post(
        "/api/units",
        json={
            "code": f"STU-{uuid.uuid4().hex[:6]}",
            "full_name": "Other Student",
            "unit_type": "student",
            "registered_location_id": sample_location["id"],
            "scan_location_ids": [sample_location["id"]],
        },
        headers=_auth(admin_token),
    )
    assert other.status_code == 201, other.text
    mine = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    theirs = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=other.json()["id"])

    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [mine["id"], theirs["id"]],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_receipt_rejects_draft_and_empty_invoices(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    await _enroll_two_months(client, admin_token, sample_unit["id"])
    listed = await client.get("/api/tuition-invoices?year=2026&month=6", headers=_auth(admin_token))
    draft_id = listed.json()[0]["id"]

    empty = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [],
        },
        headers=_auth(admin_token),
    )
    assert empty.status_code == 422

    draft = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [draft_id],
        },
        headers=_auth(admin_token),
    )
    assert draft.status_code == 422


@pytest.mark.asyncio
async def test_create_receipt_rejects_already_paid_invoice(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    first = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_second_receipt_same_day_gets_suffix(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    first_inv = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"], date="2026-09-01", fee=50
    )
    second_inv = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"], date="2026-09-03", fee=60
    )
    first = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [first_inv["id"]],
        },
        headers=_auth(admin_token),
    )
    second = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "FPS",
            "receipt_date": "2026-09-02",
            "invoice_ids": [second_inv["id"]],
        },
        headers=_auth(admin_token),
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["receipt_no"] == "R260902"
    assert second.json()["receipt_no"] == "R260902-2"


@pytest.mark.asyncio
async def test_void_receipt_reopens_invoices(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    created = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201, created.text

    voided = await client.post(
        f"/api/tuition-receipts/{created.json()['id']}/void",
        headers=_auth(admin_token),
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["status"] == "void"

    fetched = await client.get(f"/api/tuition-invoices/{invoice['id']}", headers=_auth(admin_token))
    assert fetched.json()["status"] == "issued"
    assert fetched.json()["receipt_no"] is None

    again = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-03",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert again.status_code == 201, again.text


@pytest.mark.asyncio
async def test_patch_cannot_mark_invoice_paid(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    paid = await client.patch(
        f"/api/tuition-invoices/{invoice['id']}",
        json={"status": "paid"},
        headers=_auth(admin_token),
    )
    assert paid.status_code == 422
    assert (await client.get(f"/api/tuition-invoices/{invoice['id']}", headers=_auth(admin_token))).json()[
        "status"
    ] == "issued"


@pytest.mark.asyncio
async def test_walk_in_receipt_uses_invoice_ids_not_name_match(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    a = await _manual_invoice(client, admin_token, sample_location["id"], name="Walk In A", fee=80)
    b = await _manual_invoice(client, admin_token, sample_location["id"], name="Walk In B", fee=90)

    mixed = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [a["id"], b["id"]],
        },
        headers=_auth(admin_token),
    )
    assert mixed.status_code == 422

    ok = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "payer_name": "Walk In A",
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [a["id"]],
        },
        headers=_auth(admin_token),
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["payer_name"] == "Walk In A"


@pytest.mark.asyncio
async def test_open_invoices_and_list_receipts(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    opened = await client.get(
        "/api/tuition-receipts/open-invoices",
        params={"location_id": sample_location["id"], "invoice_id": invoice["id"]},
        headers=_auth(admin_token),
    )
    assert opened.status_code == 200, opened.text
    assert {row["id"] for row in opened.json()} == {invoice["id"]}

    created = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "HSBC",
            "receipt_date": "2026-09-18",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201, created.text

    listed = await client.get(
        "/api/tuition-receipts",
        params={"year": 2026, "month": 9, "location_id": sample_location["id"]},
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["id"] == created.json()["id"]

    peeked = await client.get(
        "/api/tuition-receipts/next-no",
        params={"location_id": sample_location["id"], "date": "2026-09-18"},
        headers=_auth(admin_token),
    )
    assert peeked.status_code == 200, peeked.text
    assert peeked.json()["next_no"] == "R260918-2"


@pytest.mark.asyncio
async def test_open_invoices_rejects_unissued_seed(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    paid = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert paid.status_code == 201, paid.text

    opened = await client.get(
        "/api/tuition-receipts/open-invoices",
        params={"location_id": sample_location["id"], "invoice_id": invoice["id"]},
        headers=_auth(admin_token),
    )
    assert opened.status_code == 422


@pytest.mark.asyncio
async def test_open_invoices_walk_in_returns_only_seed(
    client: AsyncClient, admin_token: str, sample_location: dict
) -> None:
    a = await _manual_invoice(client, admin_token, sample_location["id"], name="Same Walk-in", fee=80)
    b = await _manual_invoice(client, admin_token, sample_location["id"], name="Same Walk-in", fee=90)
    opened = await client.get(
        "/api/tuition-receipts/open-invoices",
        params={"location_id": sample_location["id"], "invoice_id": a["id"]},
        headers=_auth(admin_token),
    )
    assert opened.status_code == 200, opened.text
    assert {row["id"] for row in opened.json()} == {a["id"]}
    assert b["id"] not in {row["id"] for row in opened.json()}


@pytest.mark.asyncio
async def test_open_invoices_includes_sibling_issued_for_student(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    a = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"], date="2026-09-01", fee=50
    )
    b = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"], date="2026-09-03", fee=60
    )
    opened = await client.get(
        "/api/tuition-receipts/open-invoices",
        params={"location_id": sample_location["id"], "invoice_id": a["id"]},
        headers=_auth(admin_token),
    )
    assert opened.status_code == 200, opened.text
    assert {row["id"] for row in opened.json()} == {a["id"], b["id"]}


@pytest.mark.asyncio
async def test_create_receipt_stores_description(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "FPS",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
            "description": "Sept tuition",
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["description"] == "Sept tuition"


@pytest.mark.asyncio
async def test_create_receipt_rejects_amount_that_does_not_fit(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"], fee=100)
    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
            "amount": 80,
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422
    assert "fit" in resp.json()["detail"].lower() or "match" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_receipt_accepts_adjustment_when_amount_fits(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"], fee=100)
    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
            "amount": 80,
            "adjustments": [{"course": "Early-bird discount", "amount": -20}],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    receipt = resp.json()
    assert float(receipt["amount"]) == 80
    assert receipt["adjustments"] == [
        {"month": "", "course": "Early-bird discount", "fee": None, "qty": None, "amount": -20}
    ]
    courses = [line["course"] for line in receipt["print_lines"]]
    assert "Early-bird discount" in courses
    assert float(next(line["amount"] for line in receipt["print_lines"] if line["course"] == "Early-bird discount")) == -20


@pytest.mark.asyncio
async def test_create_receipt_rejects_adjustment_when_amount_does_not_fit(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"], fee=100)
    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
            "amount": 90,
            "adjustments": [{"course": "調整", "amount": -20}],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_voided_receipt_allows_reusing_number(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    created = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201, created.text
    receipt_id = created.json()["id"]
    receipt_no = created.json()["receipt_no"]

    voided = await client.post(
        f"/api/tuition-receipts/{receipt_id}/void",
        headers=_auth(admin_token),
    )
    assert voided.status_code == 200, voided.text

    deleted = await client.delete(
        f"/api/tuition-receipts/{receipt_id}",
        headers=_auth(admin_token),
    )
    assert deleted.status_code == 204, deleted.text

    invoice2 = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"], date="2026-09-03",
    )
    again = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice2["id"]],
        },
        headers=_auth(admin_token),
    )
    assert again.status_code == 201, again.text
    assert again.json()["receipt_no"] == receipt_no


@pytest.mark.asyncio
async def test_delete_rejects_posted_receipt(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    created = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    resp = await client.delete(
        f"/api/tuition-receipts/{created.json()['id']}",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_void_invoice_after_voided_receipt(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(client, admin_token, sample_location["id"], unit_id=sample_unit["id"])
    created = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/tuition-receipts/{created.json()['id']}/void",
        headers=_auth(admin_token),
    )
    voided = await client.patch(
        f"/api/tuition-invoices/{invoice['id']}",
        json={"status": "void"},
        headers=_auth(admin_token),
    )
    assert voided.status_code == 200, voided.text
    deleted = await client.delete(
        f"/api/tuition-invoices/{invoice['id']}",
        headers=_auth(admin_token),
    )
    assert deleted.status_code == 204, deleted.text


@pytest.mark.asyncio
async def test_receipt_for_negative_manual_invoice(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    invoice = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"], fee=-200,
    )
    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-02",
            "invoice_ids": [invoice["id"]],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert float(resp.json()["amount"]) == -200


@pytest.mark.asyncio
async def test_receipt_nets_positive_and_negative_invoices(
    client: AsyncClient, admin_token: str, sample_unit: dict, sample_location: dict
) -> None:
    charge = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"], fee=500,
    )
    credit = await _manual_invoice(
        client, admin_token, sample_location["id"], unit_id=sample_unit["id"],
        date="2026-09-03", fee=-200,
    )
    resp = await client.post(
        "/api/tuition-receipts",
        json={
            "location_id": sample_location["id"],
            "unit_id": sample_unit["id"],
            "paid_by": "Cash",
            "receipt_date": "2026-09-03",
            "invoice_ids": [charge["id"], credit["id"]],
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert float(resp.json()["amount"]) == 300
