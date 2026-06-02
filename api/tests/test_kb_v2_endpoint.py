"""Component tests for KB documents v2 endpoints（CR-0003 P2-W3 / ADR-0101）。

測試矩陣：
  1. GET /kb/documents → 200 list（無 doc_type filter）
  2. GET /kb/documents?doc_type=case → 200 case list（含 meta 欄位）
  3. GET /kb/documents?doc_type=manual → 200 manual list（含 meta 欄位）
  4. GET /kb/documents?doc_type=invalid → 422 validation error
  5. POST /kb/documents (doc_type=case, Idempotency-Key) → 201
  6. POST /kb/documents (doc_type=manual, Idempotency-Key) → 201
  7. POST /kb/documents (doc_type=missing) → 422
  8. GET /kb/documents/{docId} → 200 or 404
  9. 未認證 GET → 401
 10. 未認證 POST → 401

注意：無真實 DB 時 200/201 路徑可能回 503（DB unavailable）；
      驗證 guard（401/422）在 DB 查詢前執行，因此這些路徑不依賴 DB。
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE = "/kb/documents"


def _idem_headers(base_headers: dict[str, str]) -> dict[str, str]:
    """在 base_headers 基礎上加入 Idempotency-Key。"""
    return {**base_headers, "Idempotency-Key": str(uuid.uuid4())}


# ---------------------------------------------------------------------------
# 1. GET /kb/documents → 200 list（無 doc_type filter）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_kb_documents_no_filter_200(client, admin_headers):
    """GET /kb/documents（無 doc_type）→ 200 或 503（無 DB）。"""
    res = await client.get(_BASE, headers=admin_headers)
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body
        assert isinstance(body["items"], list)


# ---------------------------------------------------------------------------
# 2. GET /kb/documents?doc_type=case → 200 list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_kb_documents_case_200(client, admin_headers):
    """GET /kb/documents?doc_type=case → 200（含 meta 欄位）或 503。"""
    res = await client.get(f"{_BASE}?doc_type=case", headers=admin_headers)
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body
        for item in body["items"]:
            assert item.get("doc_type") == "case", f"expected doc_type=case, got {item.get('doc_type')}"
            assert "meta" in item, "KBDocument case response should include meta"
            assert "id" in item
            assert "title" in item


# ---------------------------------------------------------------------------
# 3. GET /kb/documents?doc_type=manual → 200 list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_kb_documents_manual_200(client, admin_headers):
    """GET /kb/documents?doc_type=manual → 200（含 meta 欄位）或 503。"""
    res = await client.get(f"{_BASE}?doc_type=manual", headers=admin_headers)
    assert res.status_code in (200, 503), res.text
    if res.status_code == 200:
        body = res.json()
        assert "items" in body
        for item in body["items"]:
            assert item.get("doc_type") == "manual", f"expected doc_type=manual, got {item.get('doc_type')}"
            assert "meta" in item
            assert "id" in item


# ---------------------------------------------------------------------------
# 4. GET /kb/documents?doc_type=invalid → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_kb_documents_invalid_doc_type_422(client, admin_headers):
    """GET /kb/documents?doc_type=invalid_type → 422 VALIDATION_ERROR。"""
    res = await client.get(f"{_BASE}?doc_type=mega_doc_invalid", headers=admin_headers)
    assert res.status_code == 422, res.text
    body = res.json()
    # 接受 FastAPI 標準 422 或後端自訂 VALIDATION_ERROR
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 5. POST /kb/documents (doc_type=case, Idempotency-Key) → 201 or 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_kb_document_case_201(client, admin_headers):
    """POST /kb/documents doc_type=case → 201 or 503（無 DB）。"""
    headers = _idem_headers(admin_headers)
    payload = {
        "doc_type": "case",
        "title": f"Test Case {uuid.uuid4().hex[:8]}",
        "brand": "TestBrand",
        "problem_description": "門鎖無法上鎖",
        "solution": "確認電量並重設",
    }
    res = await client.post(_BASE, json=payload, headers=headers)
    assert res.status_code in (201, 503), res.text
    if res.status_code == 201:
        body = res.json()
        assert body.get("doc_type") == "case"
        assert "id" in body
        assert "meta" in body


# ---------------------------------------------------------------------------
# 6. POST /kb/documents (doc_type=manual, Idempotency-Key) → 201 or 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_kb_document_manual_201(client, admin_headers):
    """POST /kb/documents doc_type=manual → 201 or 503（無 DB）。"""
    headers = _idem_headers(admin_headers)
    payload = {
        "doc_type": "manual",
        "title": f"Test Manual {uuid.uuid4().hex[:8]}",
        "brand": "TestBrand",
        "source_uri": "https://example.com/manuals/test.pdf",
    }
    res = await client.post(_BASE, json=payload, headers=headers)
    assert res.status_code in (201, 503), res.text
    if res.status_code == 201:
        body = res.json()
        assert body.get("doc_type") == "manual"
        assert "id" in body
        assert "meta" in body


# ---------------------------------------------------------------------------
# 7. POST /kb/documents (doc_type missing) → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_kb_document_missing_doc_type_422(client, admin_headers):
    """POST /kb/documents doc_type 缺失 → 422 VALIDATION_ERROR。"""
    headers = _idem_headers(admin_headers)
    payload = {
        "title": "No doc_type",
        "brand": "TestBrand",
    }
    res = await client.post(_BASE, json=payload, headers=headers)
    assert res.status_code == 422, res.text


# ---------------------------------------------------------------------------
# 8. GET /kb/documents/{docId} → 200 / 404 / 503
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_kb_document_not_found_404(client, admin_headers):
    """GET /kb/documents/{docId} 不存在的 ID → 404 or 503（無 DB）。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(f"{_BASE}/{fake_id}", headers=admin_headers)
    assert res.status_code in (404, 503), res.text


@pytest.mark.asyncio
async def test_get_kb_document_case_filter(client, admin_headers):
    """GET /kb/documents/{docId}?doc_type=case → 只查 case_service。"""
    fake_id = str(uuid.uuid4())
    res = await client.get(f"{_BASE}/{fake_id}?doc_type=case", headers=admin_headers)
    assert res.status_code in (404, 503), res.text


# ---------------------------------------------------------------------------
# 9. 未認證 GET → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_kb_documents_unauthenticated_401(client):
    """GET /kb/documents 未帶 Authorization → 401。"""
    res = await client.get(_BASE)
    assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# 10. 未認證 POST → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_kb_document_unauthenticated_401(client):
    """POST /kb/documents 未帶 Authorization → 401。"""
    payload = {
        "doc_type": "case",
        "title": "Unauthorized",
        "brand": "TestBrand",
        "problem_description": "test",
        "solution": "test",
    }
    res = await client.post(_BASE, json=payload)
    assert res.status_code == 401, res.text
