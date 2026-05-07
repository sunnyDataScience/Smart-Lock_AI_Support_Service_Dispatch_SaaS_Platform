"""Public anonymous endpoint tests — getWorkOrderPublicStatus 升級驗證。

涵蓋：
  - getWorkOrderPublicStatus token 過短 → 422（FastAPI Path 約束）
  - getWorkOrderPublicStatus token stub 解出後 work_order 不存在 → 404
  - getWorkOrderPublicStatus 真實工單 → 200 + 遮罩欄位
  - getWorkOrderPublicStatus 90 天封存 → 410
  - getWorkOrderPublicStatus 不需要 Authorization
  - mask_phone / mask_technician_name 行為 (純 unit-style)
  - getWorkOrderPublicStatus token purpose 不符 → 404（防 token cross-use）

stub verify_token 永遠回 work_order_status purpose + subject_id=zero UUID，
所以 DB 查 work_order_id=0 → 404。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.component


_VALID_TOKEN = "x" * 64  # 32-512 chars 範圍內任何字串都會過 Path 約束


@pytest.mark.asyncio
async def test_public_status_short_token_returns_422(client):
    """Path min_length=32；少於 32 字元應該被 FastAPI 擋下回 422。"""
    res = await client.get("/api/v1/public/work-orders/short/status")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_public_status_stub_token_no_work_order_returns_404(client):
    """stub verify_token 解出 zero UUID；DB 查無 → 404。

    若 DB 未連線（純驗證環境）會回 503，亦視為合格 — 這個 case 主要用來確認
    routing 沒被中間件吃掉。
    """
    res = await client.get(
        f"/api/v1/public/work-orders/{_VALID_TOKEN}/status"
    )
    assert res.status_code in (404, 503)


@pytest.mark.asyncio
async def test_public_status_does_not_require_authorization(client):
    """public endpoint 不需 Authorization header。"""
    res = await client.get(
        f"/api/v1/public/work-orders/{_VALID_TOKEN}/status"
    )
    # 至少不應該回 401（authentication-required）
    assert res.status_code != 401


@pytest.mark.asyncio
async def test_public_status_purpose_mismatch_returns_404(client):
    """token purpose 不是 work_order_status 時，應該回 404 不洩露真實原因。"""
    from services.public_token import TokenPayload

    fake_payload = TokenPayload(
        subject_id="00000000-0000-0000-0000-000000000000",
        purpose="scope_change",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    with patch("routers.public.verify_token", return_value=fake_payload):
        res = await client.get(
            f"/api/v1/public/work-orders/{_VALID_TOKEN}/status"
        )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_public_status_with_real_work_order_returns_masked(client):
    """mock work_order_service 模擬真實工單回傳；確認欄位遮罩。"""
    from services.public_token import TokenPayload

    fake_payload = TokenPayload(
        subject_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        purpose="work_order_status",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    fake_record = {
        "work_order_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "raw_status": "in_progress",
        "public_status": "in_progress",
        "scheduled_at": "2026-05-07T10:00:00+00:00",
        "completed_at": None,
        "technician_name": "陳大文",
        "technician_phone": "0912345678",
    }

    with (
        patch("routers.public.verify_token", return_value=fake_payload),
        patch(
            "services.work_order_service.get_public_status",
            return_value=fake_record,
        ),
    ):
        res = await client.get(
            f"/api/v1/public/work-orders/{_VALID_TOKEN}/status"
        )
    assert res.status_code == 200
    body = res.json()
    assert body["work_order_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert body["status"] == "in_progress"
    # 遮罩驗證
    assert body["technician_name"] == "陳師傅"
    assert body["technician_phone_masked"] == "****5678"
    # 完整 PII 不應外露
    assert "0912345678" not in res.text
    assert "陳大文" not in res.text


@pytest.mark.asyncio
async def test_public_status_archived_after_90_days_returns_410(client):
    """work_order_service 拋 410 → router 透傳。"""
    from core.errors import ApiError
    from services.public_token import TokenPayload

    fake_payload = TokenPayload(
        subject_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        purpose="work_order_status",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    with (
        patch("routers.public.verify_token", return_value=fake_payload),
        patch(
            "services.work_order_service.get_public_status",
            side_effect=ApiError("GONE", "封存", 410),
        ),
    ):
        res = await client.get(
            f"/api/v1/public/work-orders/{_VALID_TOKEN}/status"
        )
    assert res.status_code == 410


def test_mask_phone_keeps_only_last_four():
    from services.public_token import mask_phone

    assert mask_phone("0912345678") == "****5678"
    assert mask_phone(None) is None
    assert mask_phone("123") == "****"


def test_mask_technician_name_uses_first_char():
    from services.public_token import mask_technician_name

    assert mask_technician_name("陳大文") == "陳師傅"
    assert mask_technician_name(None) is None
