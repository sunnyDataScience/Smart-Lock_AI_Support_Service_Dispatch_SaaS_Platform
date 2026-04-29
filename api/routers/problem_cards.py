"""ProblemCards router — 2 endpoints (read-only)。

operationId 對齊 openapi.yaml：
  listProblemCards, getProblemCard

寫入路徑（create/update/export）暫不實作，待寫入需求明確再開。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from core.deps import CurrentUser, require_tenant
from models.generated import ProblemCard, ProblemCardEnvelope, ProblemCardPage
from services import problem_card_service

router = APIRouter()


@router.get(
    "/problem-cards",
    operation_id="listProblemCards",
    summary="問題卡列表（cursor 分頁）",
    response_model=ProblemCardPage,
)
async def list_problem_cards(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    conversation_id: str | None = Query(default=None, description="過濾特定對話下的問題卡"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await problem_card_service.list_cards(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        conversation_id=conversation_id,
    )
    return {
        "items": [ProblemCard(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.get(
    "/problem-cards/{id}",
    operation_id="getProblemCard",
    summary="問題卡詳情",
    response_model=ProblemCardEnvelope,
)
async def get_problem_card(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    card = await problem_card_service.get_card(
        tenant_id=user.tenant_id, pc_id=id,
    )
    return {"data": ProblemCard(**card).model_dump(mode="json")}
