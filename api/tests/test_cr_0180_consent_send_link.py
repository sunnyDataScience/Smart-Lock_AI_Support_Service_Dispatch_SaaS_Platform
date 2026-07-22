"""CR-0180 免責簽署連結 LINE 推播 — send_sign_link 測試（component，需真 DB）。

驗證：
- 推播文字含 /consent/ 連結，token 可 verify 且 purpose=work_order_status、sub=wo_id
- 客戶非 LINE 用戶（channel='none'）仍回 public_path（後台複製備援）
- 越租戶 404（defense-in-depth）
- 事件留痕：work_order_events 一筆 event_type='other' + payload.kind='consent_link_sent'，
  只存 token_hash 不存完整 token
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

import core.db as db_module
from core.errors import ApiError
from services import consent_service, public_token
from tests.conftest import DEFAULT_TENANT_ID
from tests.test_cr_0033_consent import _cleanup, _seed_wo

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_send_sign_link_pushes_valid_token(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        with patch(
            "services.line_push_service.push_to_work_order_customer",
            new_callable=AsyncMock, return_value=(True, "line"),
        ) as mp:
            out = await consent_service.send_sign_link(
                work_order_id=woid, tenant_id=DEFAULT_TENANT_ID,
            )
        assert out["notification_sent"] is True
        assert out["channel"] == "line"
        # 推播文字含簽署連結，token 驗證後指回同一張工單
        text = mp.call_args.kwargs["text"]
        assert "/consent/" in text
        token = text.split("/consent/")[1].split("\n")[0].strip()
        payload = public_token.verify_token(token)
        assert payload.purpose == "work_order_status"
        assert payload.subject_id == woid
        # 事件留痕：other + kind，且不落完整 token（只有 hash）
        row = await (await db_module._conn.execute(
            "SELECT payload FROM work_order_events "
            "WHERE work_order_id = %s::uuid AND event_type = 'other' "
            "ORDER BY created_at DESC LIMIT 1", (woid,))).fetchone()
        assert row is not None
        assert row[0]["kind"] == "consent_link_sent"
        assert row[0]["token_hash"] and token not in str(row[0])
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_order_events WHERE work_order_id = %s::uuid", (woid,))
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_send_sign_link_no_line_returns_path(client):
    """客戶未綁 LINE（channel='none'）→ 不算失敗，回 public_path 供後台複製。"""
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        with patch(
            "services.line_push_service.push_to_work_order_customer",
            new_callable=AsyncMock, return_value=(False, "none"),
        ):
            out = await consent_service.send_sign_link(
                work_order_id=woid, tenant_id=DEFAULT_TENANT_ID,
            )
        assert out["notification_sent"] is False
        assert out["channel"] == "none"
        assert out["public_path"].startswith("/consent/")
    finally:
        await db_module._conn.execute(
            "DELETE FROM work_order_events WHERE work_order_id = %s::uuid", (woid,))
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_send_sign_link_wrong_tenant_404(client):
    assert await db_module._ensure_conn()
    woid, ids = await _seed_wo()
    try:
        with pytest.raises(ApiError) as ei:
            await consent_service.send_sign_link(
                work_order_id=woid,
                tenant_id="00000000-0000-0000-0000-000000000099",
            )
        assert ei.value.status_code == 404
    finally:
        await _cleanup(ids)
