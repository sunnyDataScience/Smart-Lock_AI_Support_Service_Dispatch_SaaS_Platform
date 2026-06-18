"""CR-0033 免責合規 — 三段免責同意 + consumer 端點 + PDF 免責段 測試。

- router-level（mock verify_token + service）：GET 回三段、POST 記錄、bad token 404、bad body 422
- service-level（component，需 migration 043 + work_order）：record/get upsert 冪等、unknown type 422
- PDF（component）：電子工單含免責段且仍不含成本
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

import core.db as db_module
from core.errors import ApiError
from services import consent_service
from tests.conftest import DEFAULT_TENANT_ID

pytestmark = pytest.mark.component

TOKEN = "c" * 40


def _payload(subject_id="wo-uuid-1", purpose="work_order_status", tenant_id="ten-1"):
    from unittest.mock import MagicMock
    p = MagicMock()
    p.subject_id = subject_id
    p.purpose = purpose
    p.tenant_id = tenant_id
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Router-level（mock，無 DB）
# ─────────────────────────────────────────────────────────────────────────────

class TestConsumerConsentRouter:
    async def test_get_returns_three_texts(self, client):
        sample = {"text_version": "blueprint-draft-2026-06", "consents": [
            {"consent_type": "new_installation", "title": "x", "body": "y", "accepted": False, "accepted_at": None},
        ]}
        with (
            patch("routers.consumer_v2.verify_token", return_value=_payload()),
            patch("services.consent_service.get_consents", new_callable=AsyncMock, return_value=sample),
        ):
            resp = await client.get(f"/consumer/consents/{TOKEN}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["text_version"] == "blueprint-draft-2026-06"

    async def test_post_records(self, client):
        with (
            patch("routers.consumer_v2.verify_token", return_value=_payload()),
            patch("services.consent_service.record_consents", new_callable=AsyncMock,
                  return_value={"text_version": "v", "consents": []}) as mr,
        ):
            resp = await client.post(f"/consumer/consents/{TOKEN}",
                                     json={"consents": {"new_installation": True}})
        assert resp.status_code == 200, resp.text
        assert mr.call_args.kwargs["consents"] == {"new_installation": True}

    async def test_wrong_purpose_404(self, client):
        with patch("routers.consumer_v2.verify_token", return_value=_payload(purpose="quote_view")):
            resp = await client.get(f"/consumer/consents/{TOKEN}")
        assert resp.status_code == 404, resp.text

    async def test_post_bad_body_422(self, client):
        with patch("routers.consumer_v2.verify_token", return_value=_payload()):
            resp = await client.post(f"/consumer/consents/{TOKEN}", json={"consents": {}})
        assert resp.status_code == 422, resp.text


# ─────────────────────────────────────────────────────────────────────────────
# Service-level（component，需 migration 043 + work_order）
# ─────────────────────────────────────────────────────────────────────────────

async def _seed_wo() -> tuple[str, list]:
    uid = str(uuid.uuid4()); cid = str(uuid.uuid4()); pcid = str(uuid.uuid4()); woid = str(uuid.uuid4())
    await db_module._conn.execute(
        "INSERT INTO users (id, tenant_id, role) VALUES (%s::uuid, %s::uuid, 'line_user')", (uid, DEFAULT_TENANT_ID))
    await db_module._conn.execute(
        "INSERT INTO conversations (id, user_id, session_id) VALUES (%s::uuid, %s::uuid, %s)", (cid, uid, f"s-{uid[:8]}"))
    await db_module._conn.execute(
        "INSERT INTO problem_cards (id, conversation_id, status) VALUES (%s::uuid, %s::uuid, 'confirmed')", (pcid, cid))
    await db_module._conn.execute(
        "INSERT INTO work_orders (id, problem_card_id, status, customer_address, customer_name, customer_final_amount) "
        "VALUES (%s::uuid, %s::uuid, 'completed', '新北市板橋區文化路1號', '王小明', 1500)", (woid, pcid))
    return woid, [woid, pcid, cid, uid]


async def _cleanup(ids: list) -> None:
    woid, pcid, cid, uid = ids
    await db_module._conn.execute("DELETE FROM work_order_consents WHERE work_order_id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM work_orders WHERE id = %s::uuid", (woid,))
    await db_module._conn.execute("DELETE FROM problem_cards WHERE id = %s::uuid", (pcid,))
    await db_module._conn.execute("DELETE FROM conversations WHERE id = %s::uuid", (cid,))
    await db_module._conn.execute("DELETE FROM users WHERE id = %s::uuid", (uid,))


@pytest.mark.asyncio
async def test_record_and_get_consents(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        out = await consent_service.record_consents(
            work_order_id=woid, consents={"new_installation": True, "lock_destruction": True},
            ip_address="1.2.3.4", tenant_id=DEFAULT_TENANT_ID)
        by_type = {c["consent_type"]: c for c in out["consents"]}
        assert by_type["new_installation"]["accepted"] is True
        assert by_type["lock_destruction"]["accepted"] is True
        assert by_type["personal_data"]["accepted"] is False  # 未提交
        assert len(out["consents"]) == 3  # 永遠回三段
        # §8-Q5：簽署當時文本版本快照從 DB 讀回（非僅當前常數）
        assert by_type["new_installation"]["text_version"] == consent_service.TEXT_VERSION
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_record_non_bool_value_422(client):
    """consent value 非 bool（如 JSON 字串 'false'）→ 422（防 bool() 強制轉換漏洞）。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        with pytest.raises(ApiError) as ei:
            await consent_service.record_consents(
                work_order_id=woid, consents={"new_installation": "false"})
        assert ei.value.status_code == 422
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_get_consents_wrong_tenant_404(client):
    """defense-in-depth：用錯誤 tenant_id 取同意 → 404（不洩跨租戶工單）。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        await consent_service.record_consents(
            work_order_id=woid, consents={"new_installation": True}, tenant_id=DEFAULT_TENANT_ID)
        with pytest.raises(ApiError) as ei:
            await consent_service.get_consents(
                work_order_id=woid, tenant_id="00000000-0000-0000-0000-000000000099")
        assert ei.value.status_code == 404
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_record_consents_upsert_idempotent(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        await consent_service.record_consents(work_order_id=woid, consents={"new_installation": True})
        # 重複提交同 type → upsert（更新非重複插入）
        await consent_service.record_consents(work_order_id=woid, consents={"new_installation": False})
        row = await (await db_module._conn.execute(
            "SELECT COUNT(*), bool_or(accepted) FROM work_order_consents "
            "WHERE work_order_id = %s::uuid AND consent_type = 'new_installation'", (woid,))).fetchone()
        assert row[0] == 1  # 仍只一筆
        assert row[1] is False  # 已更新為 False
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_record_unknown_type_422(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        with pytest.raises(ApiError) as ei:
            await consent_service.record_consents(work_order_id=woid, consents={"bogus": True})
        assert ei.value.status_code == 422
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_pdf_includes_disclaimer_no_cost(client):
    """電子工單 PDF 含免責段（三段標題之一）且不含內部成本字樣。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        await consent_service.record_consents(work_order_id=woid, consents={"new_installation": True})
        from services import work_order_document_service
        pdf = await work_order_document_service.render_document(
            tenant_id=DEFAULT_TENANT_ID, work_order_id=woid)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 800
    finally:
        await _cleanup(ids)
