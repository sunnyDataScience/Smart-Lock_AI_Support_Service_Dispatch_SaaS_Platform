"""M16 Consumer v2 端點元件測試（CR-0002-α / spec-alignment P2-α）。

對齊 spec: GET /consumer/work-orders/{trackingToken}
           operationId: getConsumerWorkOrderV2 (M16 FR-0022)

⚠ 本檔為 @pytest.mark.component，需 live DB（dev 環境）。
  若 DB 不可用，這些測試會在 fixture 階段 error/skip — 屬預期行為。

設計說明：
  - consumer endpoint 是 public token-based 存取，不帶 JWT / X-Tenant-ID。
  - token 驗證由 services/public_token.py::verify_token 處理（HMAC-SHA256）。
  - 測試矩陣使用 unittest.mock patch service 層，避免需要真實 signed token。

測試矩陣：
  1. 有效 token（mock verify_token + get_public_status）→ 200 + ConsumerWOView 格式
  2. 無效 / 過期 token → 404（TokenInvalidError）
  3. purpose 不符（非 work_order_status）→ 404（cross-use 防護）
  4. 工單不存在 → 404（service 回 None）
  5. 確認舊 GET /api/v1/public/work-orders/{token}/status 仍有效（雙掛過渡）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.component

# ────────────────────────────────────────────────────────────────────────────
# 常數
# ────────────────────────────────────────────────────────────────────────────

V2_PATH_PREFIX = "/consumer/work-orders/"
LEGACY_PATH_PREFIX = "/api/v1/public/work-orders/"
LEGACY_PATH_SUFFIX = "/status"

# 最短 32 字元的測試用 token（不需真實 HMAC）
VALID_TOKEN = "a" * 40
INVALID_TOKEN = "b" * 40
BAD_PURPOSE_TOKEN = "c" * 40
MISSING_WO_TOKEN = "d" * 40


# ────────────────────────────────────────────────────────────────────────────
# Mock helpers
# ────────────────────────────────────────────────────────────────────────────

def _mock_payload(subject_id: str = "wo-uuid-0001", purpose: str = "work_order_status"):
    """產假 TokenPayload mock。"""
    payload = MagicMock()
    payload.subject_id = subject_id
    payload.purpose = purpose
    return payload


_SAMPLE_WO_RECORD = {
    "work_order_id": "550e8400-e29b-41d4-a716-446655440000",
    "raw_status": "on_the_way",
    "public_status": "on_the_way",
    "scheduled_at": "2026-06-01T09:00:00+00:00",
    "completed_at": None,
    "technician_name": "陳大文",
    "technician_phone": "0912345678",
}


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────


class TestGetConsumerWorkOrderV2:
    """GET /consumer/work-orders/{trackingToken}"""

    async def test_valid_token_200(self, client):
        """有效 token + 工單存在 → 200 + ConsumerWOView 格式（無 PII）。"""
        mock_payload = _mock_payload()

        with (
            patch(
                "routers.consumer_v2.verify_token",
                return_value=mock_payload,
            ),
            patch(
                "services.work_order_service.get_public_status",
                new_callable=AsyncMock,
                return_value=_SAMPLE_WO_RECORD,
            ),
        ):
            resp = await client.get(f"{V2_PATH_PREFIX}{VALID_TOKEN}")

        assert resp.status_code == 200, resp.text
        body = resp.json()

        # ConsumerWOView 欄位檢查
        assert "work_order_state" in body
        assert body["work_order_state"] == "on_the_way"
        assert "eta_minutes" in body
        assert "technician_display_name" in body
        assert "last_update_at" in body

        # PII 保護：不得包含未 mask 的電話
        assert "0912345678" not in str(body)
        # technician_display_name 應為遮罩後（陳師傅）或 None
        display_name = body.get("technician_display_name")
        if display_name is not None:
            assert display_name in {"陳師傅", "C. Master"}, (
                f"Expected masked name, got: {display_name!r}"
            )

    async def test_invalid_token_404(self, client):
        """token 驗證失敗（TokenInvalidError）→ 404。"""
        from services.public_token import TokenInvalidError

        with patch(
            "routers.consumer_v2.verify_token",
            side_effect=TokenInvalidError("bad sig"),
        ):
            resp = await client.get(f"{V2_PATH_PREFIX}{INVALID_TOKEN}")

        assert resp.status_code == 404, resp.text

    async def test_expired_token_404(self, client):
        """token 已過期（TokenExpiredError）→ 404（不暴露 410 差異）。"""
        from services.public_token import TokenExpiredError

        with patch(
            "routers.consumer_v2.verify_token",
            side_effect=TokenExpiredError("expired"),
        ):
            resp = await client.get(f"{V2_PATH_PREFIX}{INVALID_TOKEN}")

        assert resp.status_code == 404, resp.text

    async def test_wrong_purpose_token_404(self, client):
        """token purpose 不符（scope_change token 用於工單追蹤）→ 404。"""
        mock_payload = _mock_payload(purpose="scope_change")

        with patch(
            "routers.consumer_v2.verify_token",
            return_value=mock_payload,
        ):
            resp = await client.get(f"{V2_PATH_PREFIX}{BAD_PURPOSE_TOKEN}")

        assert resp.status_code == 404, resp.text

    async def test_work_order_not_found_404(self, client):
        """token 有效但工單不存在（service 回 None）→ 404。"""
        mock_payload = _mock_payload(subject_id="nonexistent-wo-id")

        with (
            patch(
                "routers.consumer_v2.verify_token",
                return_value=mock_payload,
            ),
            patch(
                "services.work_order_service.get_public_status",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            resp = await client.get(f"{V2_PATH_PREFIX}{MISSING_WO_TOKEN}")

        assert resp.status_code == 404, resp.text

    async def test_no_auth_header_required(self, client):
        """consumer endpoint 不需要 Authorization / X-Tenant-ID header。"""
        mock_payload = _mock_payload()

        with (
            patch(
                "routers.consumer_v2.verify_token",
                return_value=mock_payload,
            ),
            patch(
                "services.work_order_service.get_public_status",
                new_callable=AsyncMock,
                return_value=_SAMPLE_WO_RECORD,
            ),
        ):
            # 刻意不帶任何 auth header
            resp = await client.get(
                f"{V2_PATH_PREFIX}{VALID_TOKEN}",
                headers={},
            )

        assert resp.status_code == 200, resp.text


class TestLegacyPublicEndpointStillWorks:
    """舊 GET /api/v1/public/work-orders/{token}/status 仍有效（雙掛過渡）。"""

    async def test_legacy_endpoint_not_gone(self, client):
        """舊端點回 200 或 404（任一），但不得 404 with 'path not found' — endpoint 存在。

        本測試只驗證路由已掛載（legacy router 未被刪除）。
        由於 token 無效 → 路由存在 → 返回 404（token invalid），而非 404（路由不存在）。
        """
        mock_payload = _mock_payload()

        with (
            patch(
                "routers.public._verify_or_404",
                return_value=mock_payload,
            ),
            patch(
                "services.work_order_service.get_public_status",
                new_callable=AsyncMock,
                return_value=_SAMPLE_WO_RECORD,
            ),
        ):
            resp = await client.get(
                f"{LEGACY_PATH_PREFIX}{VALID_TOKEN}{LEGACY_PATH_SUFFIX}"
            )

        # legacy endpoint 存在且回 200（mock 通過）
        assert resp.status_code == 200, (
            f"Legacy endpoint should still exist and return 200 with mock, got {resp.status_code}: {resp.text}"
        )
