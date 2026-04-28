"""Knowledge Base Manuals router — listManuals (read-only)。

operationId 對齊 openapi.yaml：
  listManuals

不含 deleteManual / startKbExport — 等 PDF 解析寫入 pipeline 接入後再開放。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from core.deps import CurrentUser, require_tenant
from models.generated import Manual, ManualPage
from services import manual_service

router = APIRouter()


@router.get(
    "/knowledge-base/manuals",
    operation_id="listManuals",
    summary="手冊列表（cursor 分頁）",
    response_model=ManualPage,
)
async def list_manuals(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    brand: str | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await manual_service.list_manuals(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        brand=brand,
    )
    return {
        "items": [Manual(**m).model_dump(mode="json") for m in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }
