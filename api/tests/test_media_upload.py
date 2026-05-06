"""媒體上傳 + 下載 + 列表整合測試（v1.25.0 / v1.27.0 / v1.28.0）。"""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_upload_and_get_image(client, admin_headers):
    # 假 PNG header bytes
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    files = {"file": ("test.png", fake_png, "image/png")}
    data = {"purpose": "other"}
    res = await client.post(
        "/api/v1/media", headers=admin_headers, files=files, data=data
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(fake_png)
    assert body["url"].startswith("/api/v1/media/")
    media_id = body["id"]

    # GET 下載
    res2 = await client.get(
        f"/api/v1/media/{media_id}", headers=admin_headers
    )
    assert res2.status_code == 200
    assert res2.headers["content-type"] == "image/png"
    assert res2.content == fake_png


@pytest.mark.asyncio
async def test_upload_invalid_purpose(client, admin_headers):
    fake = b"\x89PNG\r\n"
    files = {"file": ("x.png", fake, "image/png")}
    data = {"purpose": "invalid_type"}
    res = await client.post(
        "/api/v1/media", headers=admin_headers, files=files, data=data
    )
    # FastAPI Literal validation → 422
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_unsupported_content_type(client, admin_headers):
    fake = b"hello world"
    files = {"file": ("doc.txt", fake, "text/plain")}
    data = {"purpose": "other"}
    res = await client.post(
        "/api/v1/media", headers=admin_headers, files=files, data=data
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_media_404(client, admin_headers):
    bogus_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/media/{bogus_id}", headers=admin_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_media_for_dispute_returns_items_array(client, admin_headers):
    """空 dispute_id 應回傳 items=[] 而非報錯。"""
    bogus = str(uuid.uuid4())
    res = await client.get(
        f"/api/v1/disputes/{bogus}/media", headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["items"] == []
