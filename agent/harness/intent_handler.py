"""H_INTENT — F-014/F-015 LINE 自助路徑 handler (ADR-009 §8 D1 dual-trigger a path).

呼叫時機：``orchestrator.agent_and_reply`` 在 H_QR quick_reply 之後 / agent
invocation 之前。intent 命中時 short-circuit 整個 pipeline（避免 AI 仍給技術
建議跟客戶意圖打架），直接 reply 申請受理確認。

V1.0 minimum 策略（為何不直接 create_refund_request / create_warranty_claim）：

- F-014 RefundRequest schema required fields: ``work_order_id``、``amount``、
  ``reason_code``。LINE 端只有 line_user_id 與訊息文字，沒有 WO id；
  ``listWorkOrders`` admin endpoint 也未支援 ``by_line_user`` filter。
- F-015 WarrantyClaim 同樣 required ``customer_id`` (UUID)，LINE 端無法解出。
- 強行用 placeholder UUID 會被 admin api 422 拒；fail-soft 會落 outbox
  但 outbox 也是無效 payload（worker 補打仍會 422）。

決策：V1.0 不直接寫 admin tables，改走 dual-trigger (b) path：
1. intent 命中 → 寫一筆 audit log（CS 在 admin 看 conversation 時可見）
2. reply 客戶「申請已收到，客服將於 24h 內審理」+ short-circuit pipeline
3. CS 看到 LINE 訊息 → 在 admin 主動代開 refund/warranty（既有 dual-trigger
   (b) path UI 已實作於 web/，本 commit 之外）

V1.1 升級：
- 加 ``listWorkOrdersByLineUser`` admin endpoint（OpenAPI 改 schema）
- intent 命中 + 找到最近 completed WO → call ``create_refund_request``
  並在 reply 帶 ``document_number``
- ``customer_id`` 由 conversation → user 對應表查（admin 端 schema 補）

Layering: harness-tier，可 import harness / core，不可 import agent。
"""
from __future__ import annotations

PHASE: str = "H_INTENT"  # per harness/__init__.py PIPELINE inventory (ADR-0024 §3 S2)

import logging

from harness.intent_classifier import detect_intent

logger = logging.getLogger("agent.harness.intent_handler")


# Reply templates（V1.0 不含 doc_number；V1.1 整合 create_*  後改成
# f-string 帶入 ``document_number``）。
_REPLY_REFUND = (
    "您的退款申請已收到，客服將於 24 小時內審理並回覆。\n"
    "若需立即協助，請來電 02-2627-1789（服務時間 09:00-18:00）。"
)
_REPLY_WARRANTY = (
    "您的保固申訴已收到，技術團隊將於 24 小時內回覆。\n"
    "若需立即協助，請來電 02-2627-1789（服務時間 09:00-18:00）。"
)


async def try_handle_intent(
    *,
    user_id: str,
    text: str,
    audit_storage=None,
) -> str | None:
    """偵測 refund/warranty intent，命中即回 reply 文字（呼叫端 send + return early）。

    Args:
        user_id: line user id
        text: 本輪 user 訊息合併後的純文字（buffer items 抽 text 後 join）
        audit_storage: optional audit storage for logging intent hit (best-effort)

    Returns:
        reply text on intent hit (orchestrator should send + return), or None
        on no match (orchestrator continues normal agent flow).
    """
    intent = detect_intent(text)
    if intent is None:
        return None

    logger.info(
        "F-014/F-015 intent hit user=%s intent=%s text_preview=%r",
        user_id, intent, text[:80],
    )

    # Best-effort audit log so CS sees the LINE intent in admin even though
    # we don't write refund/warranty tables yet (V1.0 dual-trigger b path).
    if audit_storage is not None:
        try:
            log_method = getattr(audit_storage, "log_intent_hit", None)
            if callable(log_method):
                await log_method(user_id=user_id, intent=intent, text=text[:500])
        except Exception:  # noqa: BLE001 — audit is fail-soft
            logger.warning(
                "intent audit log failed user=%s intent=%s", user_id, intent,
                exc_info=True,
            )

    if intent == "refund":
        return _REPLY_REFUND
    if intent == "warranty":
        return _REPLY_WARRANTY
    return None  # unreachable; detect_intent only returns refund/warranty/None
