"""簽名端點回應信封 — 回歸守門（fix/signature-response-500）。

背景：
  `submit_work_order_signature`（v1）與 `submit_work_order_signature_v2`（v2）都宣告
  `response_model=ApiResponseGeneric`（要求 `data` 欄），但實作曾直接 `return result`，
  而 `signature_service.submit_work_order_signature` 回的是
  `{success, message, request_id}`（**無 `data`**）。**成功路徑**（雙方簽名）因此在
  FastAPI serialize_response 炸 `ResponseValidationError` → 500；錯誤往上冒到 CORS
  middleware 時回應壞掉，瀏覽器顯示「Load failed」。已用真實 curl（帶 Origin）對運行中
  stack 確認修正後回 200 + `{"data": {...}}` + 正常 ACAO header。

  既有簽名測試全用假 WO id 只測 guard（idempotency / cross-tenant / 422），從未經 HTTP
  層打成功路徑 → 此 500 是典型「CI 假綠」漏網。完整 HTTP 成功路徑需 seed
  work_orders→problem_cards→conversations→users→technicians 整條 FK 鏈，成本與脆弱度
  過高；本檔改釘住「裸 service result 不符信封、handler 必須包 data」這個不變量——
  若有人把 handler 改回 `return result`，端點成功路徑會再次 500。

DB-free、確定性，CI 可靠運行。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.generated import ApiResponseGeneric

# signature_service.submit_work_order_signature 成功時回的形狀（無 data）
_SERVICE_RESULT = {
    "success": True,
    "message": "Work order signed by both parties (2 new row(s))",
    "request_id": None,
}


def test_bare_service_result_violates_envelope():
    """裸 service result 缺 data → ApiResponseGeneric 拒絕。

    這正是修正前 handler 直接 `return result` 會在成功路徑 500 的根因。
    """
    with pytest.raises(ValidationError):
        ApiResponseGeneric(**_SERVICE_RESULT)


def test_handler_wrapped_payload_satisfies_envelope():
    """handler 修正後的 payload（data 包住 service result）→ 通過信封驗證。"""
    payload = {"data": _SERVICE_RESULT, "message": _SERVICE_RESULT["message"]}
    env = ApiResponseGeneric(**payload)
    assert env.data["success"] is True
    assert env.message == _SERVICE_RESULT["message"]


def test_handlers_wrap_service_result_in_data():
    """靜態守門：兩個 signature handler 都必須把 result 包進 data 再回，不可裸 return。

    讀 router 原始碼確認 `payload = {"data": result` 樣式存在，擋掉未來改回
    `return result` 的回歸（該寫法會讓端點成功路徑再次 ResponseValidationError 500）。
    """
    import pathlib

    api_dir = pathlib.Path(__file__).resolve().parent.parent
    for rel in ("routers/work_orders.py", "routers/work_orders_v2.py"):
        src = (api_dir / rel).read_text(encoding="utf-8")
        assert '"data": result' in src, f"{rel} signature handler 未把 result 包進 data"
