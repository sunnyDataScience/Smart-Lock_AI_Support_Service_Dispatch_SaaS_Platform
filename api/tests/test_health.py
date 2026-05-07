"""smoke test：health endpoint。"""

import pytest

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/health")
    assert res.status_code in (200, 503)
    body = res.json()
    assert "status" in body
    assert "checks" in body
