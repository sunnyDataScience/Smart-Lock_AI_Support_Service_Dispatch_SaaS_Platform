"""listScheduledReports 的角色閘門（CR-0211 D1）。

WHY：同檔三支端點——create（:41）、list（:66）、cancel（:95）——只有 list 掛的是
`require_tenant`（任何已登入的同租戶使用者），另兩支都是 `OPS_ROLES`。
這種不對稱是漏設而非設計，而回傳內容含 `recipients`（收件人 email 清單）＝PII，
等於任何技師或客服帳號都能列出整個租戶的報表收件人。
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.component
TID = "00000000-0000-0000-0000-000000000001"
PATH = f"/tenants/{TID}/scheduled-reports"  # 無 /api/v1 前綴（實際註冊路徑）


@pytest.mark.asyncio
async def test_list_scheduled_reports_allows_ops(client, admin_headers):
    """admin（OPS_ROLES 內）仍可讀 —— 收窄不得誤傷既有呼叫端。"""
    res = await client.get(PATH, headers=admin_headers)
    # 明確斷言 200 而非 `!= 403` —— 後者會讓路徑打錯的 404 假裝通過
    assert res.status_code == 200, f"admin 被擋掉了：{res.status_code} {res.text[:200]}"


@pytest.mark.asyncio
async def test_list_scheduled_reports_denies_technician(client, technician_headers):
    """技師不得列出報表排程（recipients 是 email PII）。"""
    res = await client.get(PATH, headers=technician_headers)
    assert res.status_code == 403, (
        f"技師讀得到報表排程收件人 —— PII 外洩（實得 {res.status_code}）"
    )


@pytest.mark.asyncio
async def test_list_scheduled_reports_denies_customer_service(client, customer_service_headers):
    """客服同理 —— 與同檔 create/cancel 的 OPS_ROLES 對齊。"""
    res = await client.get(PATH, headers=customer_service_headers)
    assert res.status_code == 403, f"客服讀得到報表排程收件人（實得 {res.status_code}）"
