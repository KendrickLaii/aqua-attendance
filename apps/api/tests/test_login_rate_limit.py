"""Login rate-limit storage must not leak across pytest cases.

CI runs the whole suite against one in-memory limiter keyed by 127.0.0.1.
Without a per-test reset, later fixtures (uploads) get 429 and no access_token.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _insert_test_user

LOGIN_BUDGET = 100  # matches tests/conftest.py LOGIN_RATE_LIMIT


async def _burn_login_budget(client: AsyncClient, n: int) -> None:
    for _ in range(n):
        await client.post("/api/auth/login", json={"username": "nobody", "password": "nope"})


@pytest.mark.asyncio
class TestLoginLimiterIsolation:
    async def test_01_consume_the_shared_ip_budget(self, client: AsyncClient) -> None:
        await _burn_login_budget(client, LOGIN_BUDGET)

    async def test_02_next_test_can_still_login(self, client: AsyncClient) -> None:
        uname = f"after_budget_{uuid.uuid4().hex[:8]}"
        await _insert_test_user(username=uname, email=f"{uname}@test.com")
        resp = await client.post("/api/auth/login", json={"username": uname, "password": "admin123"})
        assert resp.status_code == 200, resp.text
        assert "access_token" in resp.json()
