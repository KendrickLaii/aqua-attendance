import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_invoice_jobs_create_reuse_and_delete(client: AsyncClient, admin_token: str, sample_location: dict) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    location_id = sample_location["id"]

    created = await client.post(
        "/api/invoice-jobs",
        json={"name": "  Special review  ", "location_id": location_id},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "Special review"

    again = await client.post(
        "/api/invoice-jobs", json={"name": "special review", "location_id": location_id}, headers=headers
    )
    assert again.status_code == 200, again.text
    assert again.json()["id"] == body["id"]

    listed = await client.get("/api/invoice-jobs", params={"location_id": location_id}, headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(row["name"] == "Special review" for row in listed.json())

    removed = await client.delete(f"/api/invoice-jobs/{body['id']}", headers=headers)
    assert removed.status_code == 204

    missing = await client.delete(f"/api/invoice-jobs/{body['id']}", headers=headers)
    assert missing.status_code == 404
