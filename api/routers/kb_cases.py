"""Knowledge Base Cases router — 5 CRUD + searchCases。

operationId 對齊 openapi.yaml：
  listCases, createCase, getCase, updateCase, deleteCase, searchCases
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response, status

from core.deps import BACKOFFICE_ROLES, CurrentUser, require_tenant, role_required
from core.idempotency import idempotency_guard, IdempotencyContext
from models.generated import (
    CaseEntry,
    CaseEntryCreateRequest,
    CaseEntryEnvelope,
    CaseEntryPage,
    CaseEntryUpdateRequest,
    CaseSearchHit,
    CaseSearchRequest,
    CaseSearchResponse,
)
from services import case_service

router = APIRouter()


def _envelope(case: dict) -> dict:
    return {"data": CaseEntry(**case).model_dump(mode="json")}


@router.get(
    "/knowledge-base/cases",
    operation_id="listCases",
    summary="案例列表（cursor 分頁）",
    response_model=CaseEntryPage,
)
async def list_cases(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    brand: str | None = Query(default=None),
    verified: bool | None = Query(default=None),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    page = await case_service.list_cases(
        tenant_id=user.tenant_id,
        cursor=cursor,
        limit=limit,
        brand=brand,
        verified=verified,
    )
    return {
        "items": [CaseEntry(**c).model_dump(mode="json") for c in page["items"]],
        "next_cursor": page["next_cursor"],
        "has_more": page["has_more"],
    }


@router.post(
    "/knowledge-base/cases",
    operation_id="createCase",
    summary="建立案例",
    status_code=status.HTTP_201_CREATED,
    response_model=CaseEntryEnvelope,
)
async def create_case(
    body: CaseEntryCreateRequest,
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    case = await case_service.create_case(
        tenant_id=user.tenant_id,
        payload=body.model_dump(),
        created_by=user.user_id,
    )
    payload = _envelope(case)
    if idem is not None:
        await idem.save(201, payload)
    return payload


@router.get(
    "/knowledge-base/cases/{id}",
    operation_id="getCase",
    summary="取得案例詳情",
    response_model=CaseEntryEnvelope,
)
async def get_case(
    id: str = Path(),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    case = await case_service.get_case(tenant_id=user.tenant_id, case_id=id)
    return _envelope(case)


@router.put(
    "/knowledge-base/cases/{id}",
    operation_id="updateCase",
    summary="更新案例（整體取代）",
    response_model=CaseEntryEnvelope,
)
async def update_case(
    body: CaseEntryUpdateRequest,
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    case = await case_service.update_case(
        tenant_id=user.tenant_id,
        case_id=id,
        patch=body.model_dump(exclude_none=True),
    )
    payload = _envelope(case)
    if idem is not None:
        await idem.save(200, payload)
    return payload


@router.delete(
    "/knowledge-base/cases/{id}",
    operation_id="deleteCase",
    summary="刪除案例",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case(
    id: str = Path(),
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> Response:
    await case_service.delete_case(tenant_id=user.tenant_id, case_id=id)
    if idem is not None:
        await idem.save(204, {})
    return Response(status_code=204)


@router.post(
    "/knowledge-base/cases/search",
    operation_id="searchCases",
    summary="案例語意搜尋（Phase 1：關鍵字加權）",
    response_model=CaseSearchResponse,
)
async def search_cases(
    body: CaseSearchRequest,
    user: CurrentUser = Depends(role_required(*BACKOFFICE_ROLES)),
) -> dict:
    result = await case_service.search_cases(
        tenant_id=user.tenant_id,
        query=body.query,
        brand=body.brand,
        model=body.model,
        limit=body.limit if body.limit is not None else 5,
        similarity_threshold=(
            body.similarity_threshold
            if body.similarity_threshold is not None
            else 0.75
        ),
    )
    hits = [
        CaseSearchHit(
            case=CaseEntry(**h["case"]),
            score=h["score"],
        ).model_dump(mode="json")
        for h in result["hits"]
    ]
    return {"hits": hits}
