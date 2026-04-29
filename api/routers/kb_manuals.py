"""Knowledge Base Manuals router — listManuals + deleteManual。

operationId 對齊 openapi.yaml：
  listManuals, deleteManual

不含 uploadManual / startKbExport — 等 PDF 解析寫入 pipeline 接入後再開放。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response

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


@router.delete(
    "/knowledge-base/manuals/{id}",
    operation_id="deleteManual",
    summary="刪除手冊（連同 chunks 透過 FK CASCADE 一併移除）",
    status_code=204,
    response_class=Response,
)
async def delete_manual(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> Response:
    await manual_service.delete_manual(tenant_id=user.tenant_id, manual_id=id)
    return Response(status_code=204)
