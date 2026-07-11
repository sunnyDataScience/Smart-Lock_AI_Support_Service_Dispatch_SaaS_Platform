"""Internal service-to-service ingest router（方案 A + CR-0022）。

非人類發動、無 JWT 的內部寫入端點：
  1. `/internal/conversations/ingest`（方案 A）— LINE agent gateway 把每輪對話
     旁路持久化到 conversations/messages，使工單/對話後台能重新渲染對話歷史。
  2. `/internal/escalations/ingest`（CR-0022 / ADR-0112）— agent transfer_to_human 後
     旁路建一張 AI 草擬問題卡（source='ai_line'），供客服人審 → confirm → convert。

認證：`require_internal_token`（X-Internal-Token header 比對 INTERNAL_API_TOKEN
環境變數，fail closed）。不走 JWT/tenant header —— tenant_id 由 body 帶入。

設計原則（對齊架構鎖）：
  - agent 核心與 CS_TOOL_ALLOWLIST 不變；寫入只發生在「通道旁路」這一層。
  - 復用既有 conversation_service / problem_card_service，不重寫 SQL。
  - **AI 永不自轉工單**：本路由最多建草擬卡；confirm/convert 走客服認證端點（ADR-0028/0031）。
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from core.deps import require_internal_token
from models.internal import EscalationIngestRequest, IngestTurnRequest
from services import conversation_service, problem_card_service

logger = logging.getLogger("api.internal_ingest")

router = APIRouter()


def _resolve_tenant_id(raw: str) -> str:
    """agent 送來的 tenant 可能是人類可讀別名（如 'locksmart'）而非 UUID。

    - 合法 UUID → 原樣使用。
    - 別名 → 用 `AGENT_TENANT_ID` 環境變數對應到實際租戶 UUID（未設則 400，明確報錯而非 500）。

    單租戶 dev：所有別名對應同一個 `AGENT_TENANT_ID`；多租戶日後需改為 saas.tenant slug→UUID 查表。
    （agent 端記憶層仍以字串 tenant 為 scope key，見 CR-0023；此處只負責 API 寫入的租戶身分解析。）
    """
    try:
        return str(uuid.UUID(str(raw)))
    except (ValueError, AttributeError, TypeError):
        pass
    mapped = os.getenv("AGENT_TENANT_ID")
    if not mapped:
        raise HTTPException(
            status_code=400,
            detail=f"tenant_id '{raw}' 非 UUID，且未設定 AGENT_TENANT_ID 對應別名→租戶 UUID",
        )
    try:
        return str(uuid.UUID(mapped))
    except (ValueError, AttributeError, TypeError) as e:
        raise HTTPException(
            status_code=500, detail="AGENT_TENANT_ID 設定值不是合法 UUID"
        ) from e


@router.post(
    "/internal/conversations/ingest",
    operation_id="ingestConversationTurn",
    summary="內部：旁路持久化一輪 LINE 對話（方案 A，agent gateway 用）",
    tags=["internal"],
)
async def ingest_conversation_turn(
    body: IngestTurnRequest,
    _auth: None = Depends(require_internal_token),
) -> dict:
    result = await conversation_service.ingest_turn(
        tenant_id=_resolve_tenant_id(body.tenant_id),
        line_user_id=body.line_user_id,
        session_id=body.session_id,
        user_text=body.user_text,
        assistant_text=body.assistant_text,
        display_name=body.display_name,
        media_base64=body.media_base64,
        media_mime=body.media_mime,
        sentiment_label=body.sentiment_label,
        sentiment_confidence=body.sentiment_confidence,
        sentiment_keywords=body.sentiment_keywords,
    )
    logger.info(
        "ingest turn: conv=%s appended=%d line=%s",
        str(result.get("conversation_id"))[:8],
        result.get("messages_appended", 0),
        body.line_user_id[:8],
    )
    return {"data": result, "error": None}


@router.get(
    "/internal/conversations/handover-state",
    operation_id="getConversationHandoverState",
    summary="內部：查對話是否處於人工接管中（CR-0024，agent gateway 回覆前判斷用）",
    tags=["internal"],
)
async def get_handover_state(
    tenant_id: str = Query(..., description="租戶 UUID 或別名"),
    session_id: str = Query(..., description="對話 session_id（外部冪等鍵）"),
    _auth: None = Depends(require_internal_token),
) -> dict:
    """gateway 在跑 turn 前查此端點：escalated=true 時 AI 暫停（Phase 1 全暫停）。

    查無對話 → escalated=false（agent 照常回，fail-soft 友善預設）。
    """
    result = await conversation_service.get_handover_state(
        tenant_id=_resolve_tenant_id(tenant_id),
        session_id=session_id,
    )
    return {"data": result, "error": None}


@router.post(
    "/internal/escalations/ingest",
    operation_id="ingestEscalation",
    summary="內部：agent escalation → AI 草擬問題卡（CR-0022，agent gateway 用）",
    tags=["internal"],
)
async def ingest_escalation(
    body: EscalationIngestRequest,
    _auth: None = Depends(require_internal_token),
) -> dict:
    result = await problem_card_service.escalation_to_draft_pc(
        tenant_id=_resolve_tenant_id(body.tenant_id),
        line_user_id=body.line_user_id,
        session_id=body.session_id,
        reason=body.reason,
        is_explicit=body.is_explicit,
        facts_snapshot=body.facts_snapshot,
        display_name=body.display_name,
    )
    logger.info(
        "ingest escalation: pc=%s created=%s line=%s explicit=%s",
        str(result.get("problem_card_id"))[:8],
        result.get("created"),
        body.line_user_id[:8],
        body.is_explicit,
    )
    return {"data": result, "error": None}


@router.post(
    "/internal/quotes/{quote_id}:customer-respond",
    operation_id="customerRespondQuoteInternal",
    summary="內部：客戶經 LINE postback 同意/拒絕報價（CR-0095，agent gateway 用）",
    tags=["internal"],
)
async def customer_respond_quote(
    quote_id: str,
    body: dict,
    _auth: None = Depends(require_internal_token),
) -> dict:
    """agent 收 LINE postback（q:a|/q:r|）→ 旁路呼此端點。

    service 端先驗 line_user_id 確實是此報價客戶（防跨客戶誤同意）→ 403 不符；
    再走狀態機（accept→accepted / reject→decline→rejected）。
    """
    from services import quote_engine_service

    tenant_id = _resolve_tenant_id((body or {}).get("tenant_id", ""))
    line_user_id = (body or {}).get("line_user_id")
    decision = (body or {}).get("decision")
    if not line_user_id or decision not in {"accept", "reject"}:
        raise HTTPException(
            status_code=422,
            detail="line_user_id + decision('accept'|'reject') required",
        )
    result = await quote_engine_service.customer_respond_to_quote(
        tenant_id=tenant_id, quote_id=quote_id,
        line_user_id=line_user_id, decision=decision,
    )
    logger.info(
        "quote customer-respond: quote=%s decision=%s state=%s line=%s",
        quote_id[:8], decision, result.get("state"), line_user_id[:8],
    )
    return {"data": result, "error": None}
