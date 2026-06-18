"""CR-0032 Phase C — 客戶端報價查看（consumer quote endpoints）測試。

對齊 GET/POST /consumer/quotes/{token}（purpose=quote_view）：
  - public_token quote_view roundtrip（真 token，驗 verify_token allowlist 已含 quote_view）
  - GET：200 不洩 unit_price（結構性零成本外洩）/ purpose 不符 404 / 無效 token 404
  - POST：accept→accepted、reject→decline / 非法 decision 422

⚠ @pytest.mark.component；router-level 用 mock service + mock verify_token，
  不需真 DB（與 test_consumer_v2_endpoint.py 同模式）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.component

QUOTE_TOKEN = "q" * 40


def _payload(subject_id="quote-uuid-1", purpose="quote_view", tenant_id="ten-1"):
    p = MagicMock()
    p.subject_id = subject_id
    p.purpose = purpose
    p.tenant_id = tenant_id
    return p


_SAMPLE_QUOTE = {
    "id": "quote-uuid-1", "work_order_id": "wo-1", "version": 1, "state": "sent",
    "total_amount": "1400.00", "deposit_required": None,
    "expiry_at": "2026-07-01T00:00:00+00:00", "snapshot_hash": "abc123",
    "is_mock": True, "cost_visible": False,
    "lines": [{
        "id": "l1", "item_name": "到府檢測", "category": "labor", "quantity": 1,
        "customer_price": "800.00", "service_code": "SVC-RES-001", "material_code": None,
    }],
}


def test_quote_view_token_roundtrip():
    """真 token：generate(quote_view) → verify 通過 + purpose/tenant 保留（驗 allowlist 修正）。"""
    from services import public_token

    tok = public_token.generate_token(
        "quote-xyz", purpose="quote_view", ttl_days=7, tenant_id="ten-1")
    payload = public_token.verify_token(tok)
    assert payload.purpose == "quote_view"
    assert payload.subject_id == "quote-xyz"
    assert payload.tenant_id == "ten-1"


class TestGetConsumerQuoteV2:
    """GET /consumer/quotes/{token}"""

    async def test_valid_200_no_cost_leak(self, client):
        with (
            patch("routers.consumer_v2.verify_token", return_value=_payload()),
            patch("services.quote_engine_service.get_quote",
                  new_callable=AsyncMock, return_value=_SAMPLE_QUOTE) as mg,
        ):
            resp = await client.get(f"/consumer/quotes/{QUOTE_TOKEN}")

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["state"] == "sent"
        assert body["total_amount"] == "1400.00"
        # 結構性零成本外洩：回應不得含 unit_price
        assert "unit_price" not in str(body)
        # service 必須以 include_cost=False 呼叫（客戶端強制遮蔽）
        assert mg.call_args.kwargs["include_cost"] is False

    async def test_wrong_purpose_404(self, client):
        with patch("routers.consumer_v2.verify_token",
                   return_value=_payload(purpose="work_order_status")):
            resp = await client.get(f"/consumer/quotes/{QUOTE_TOKEN}")
        assert resp.status_code == 404, resp.text

    async def test_invalid_token_404(self, client):
        from services.public_token import TokenInvalidError

        with patch("routers.consumer_v2.verify_token",
                   side_effect=TokenInvalidError("bad sig")):
            resp = await client.get(f"/consumer/quotes/{QUOTE_TOKEN}")
        assert resp.status_code == 404, resp.text


class TestRespondConsumerQuoteV2:
    """POST /consumer/quotes/{token}"""

    async def test_accept_200(self, client):
        with (
            patch("routers.consumer_v2.verify_token", return_value=_payload()),
            patch("services.quote_engine_service.transition", new_callable=AsyncMock,
                  return_value={"id": "quote-uuid-1", "state": "accepted"}) as mt,
        ):
            resp = await client.post(f"/consumer/quotes/{QUOTE_TOKEN}",
                                     json={"decision": "accept"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["state"] == "accepted"
        assert mt.call_args.kwargs["action"] == "accept"

    async def test_reject_maps_to_decline(self, client):
        with (
            patch("routers.consumer_v2.verify_token", return_value=_payload()),
            patch("services.quote_engine_service.transition", new_callable=AsyncMock,
                  return_value={"id": "quote-uuid-1", "state": "rejected"}) as mt,
        ):
            resp = await client.post(f"/consumer/quotes/{QUOTE_TOKEN}",
                                     json={"decision": "reject"})
        assert resp.status_code == 200, resp.text
        assert mt.call_args.kwargs["action"] == "decline"

    async def test_bad_decision_422(self, client):
        with patch("routers.consumer_v2.verify_token", return_value=_payload()):
            resp = await client.post(f"/consumer/quotes/{QUOTE_TOKEN}",
                                     json={"decision": "maybe"})
        assert resp.status_code == 422, resp.text
