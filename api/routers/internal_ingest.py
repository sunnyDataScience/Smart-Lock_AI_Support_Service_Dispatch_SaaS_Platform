"""Internal service-to-service ingest router（方案 A）。

非人類發動、無 JWT 的內部寫入端點。目前僅一條：LINE agent gateway 把每輪
對話（客人訊息 + AI 回覆）旁路持久化到 conversations/messages，使工單/對話
後台能重新渲染對話歷史。

認證：`require_internal_token`（X-Internal-Token header 比對 INTERNAL_API_TOKEN
環境變數，fail closed）。不走 JWT/tenant header —— tenant_id 由 body 帶入。

設計原則（對齊架構鎖）：
  - agent 核心與 CS_TOOL_ALLOWLIST 不變；持久化只發生在「通道旁路」這一層。
  - 復用既有 conversation_service，不重寫 SQL。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from core.deps import require_internal_token
from models.internal import IngestTurnRequest
from services import conversation_service

logger = logging.getLogger("api.internal_ingest")

router = APIRouter()


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
        tenant_id=body.tenant_id,
        line_user_id=body.line_user_id,
        session_id=body.session_id,
        user_text=body.user_text,
        assistant_text=body.assistant_text,
        display_name=body.display_name,
    )
    logger.info(
        "ingest turn: conv=%s appended=%d line=%s",
        str(result.get("conversation_id"))[:8],
        result.get("messages_appended", 0),
        body.line_user_id[:8],
    )
    return {"data": result, "error": None}
