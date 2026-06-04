"""KB documents v2 router — 統一 cases + manuals (CR-0003 P2-W3, ADR-0101).

對齊 frozen spec /kb/documents + /kb/documents/{docId}：
  operationId: listKBDocuments   → GET  /kb/documents
  operationId: ingestKBDocument  → POST /kb/documents
  operationId: getKBDocument     → GET  /kb/documents/{docId}

doc_type 分派策略：
  doc_type=case   → case_service (case_entries table)
  doc_type=manual → manual_service (manuals table)

模型映射說明（TODO 與設計取捨）：
  spec KBDocument schema = {id, doc_type, tenant_scope, brand_scope, project_scope,
                             title, version, effective_date}
  case_service 輸出額外欄位 = {problem_description, solution, brand, model, tags,
                               verified, embedding_status, created_at, updated_at}
  manual_service 輸出額外欄位 = {brand, model, file_name, file_size_bytes,
                                 status(processing/ready/failed), chunk_count, created_at}

  mapping 策略：盡量對齊 KBDocument 核心欄位，額外欄位以 meta 子物件掛載；
  回傳 dict（不用 response_model 嚴格驗證，W1/W2 教訓），確保序列化不 500。

  TODO: spec KBDocument.doc_type enum=[mega_doc, manual, sop, faq] 未含 'case'；
        本 v2 擴充 doc_type='case' 對應 case_entries；待 spec 下次更新補入
        enum 值或另走 ADR-0101 §2.3 的 sop 對映決議。

POST /kb/documents (ingestKBDocument) 支援 doc_type=case 與 doc_type=manual：
  - doc_type=case  → case_service.create_case
  - doc_type=manual → manual_service.upload_manual 的 metadata-only 路徑
    （不含 file bytes；若需上傳 PDF 仍走 legacy /api/v1/knowledge-base/manuals/upload）

Deprecation：不改動 legacy router（kb_cases.py、kb_manuals.py），
  DeprecationMiddleware 統一在 /api/v1/* 掛 header。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Path, Query, status

from core.deps import CurrentUser, require_tenant
from core.errors import ApiError
from core.idempotency import IdempotencyContext, idempotency_guard
from services import case_service, manual_service

router = APIRouter()


# ---------------------------------------------------------------------------
# 內部型別別名（inline，不走 response_model 嚴格驗證 — W1/W2 教訓）
# ---------------------------------------------------------------------------

_DOC_TYPES = frozenset({"case", "manual"})

# ---------------------------------------------------------------------------
# 轉換 helpers
# ---------------------------------------------------------------------------


def _case_to_kb_document(case: dict) -> dict:
    """將 case_service 輸出轉成 KBDocument-compatible dict。

    核心欄位：id / doc_type / title / brand_scope / version / effective_date
    meta 子物件：附帶 case-specific 欄位（problem_description, solution, 等）
    TODO: effective_date 對映 created_at；待 case_entries 增 effective_date 欄位後更新。
    """
    return {
        "id": case["id"],
        "doc_type": "case",
        "title": case.get("title", ""),
        "tenant_scope": [],            # spec 欄位；case_entries 無 tenant_scope 陣列，以空陣列回傳
        "brand_scope": [case["brand"]] if case.get("brand") else [],
        "project_scope": [],
        "version": None,               # case_entries 無 version 欄位
        "effective_date": None,        # TODO: 待 case_entries 增欄
        "meta": {
            "problem_description": case.get("problem_description"),
            "solution": case.get("solution"),
            "brand": case.get("brand"),
            "model": case.get("model"),
            "tags": case.get("tags") or [],
            "verified": case.get("verified", False),
            "embedding_status": case.get("embedding_status"),
            "created_at": case.get("created_at"),
            "updated_at": case.get("updated_at"),
        },
    }


def _manual_to_kb_document(manual: dict) -> dict:
    """將 manual_service 輸出轉成 KBDocument-compatible dict。

    brand_scope 對映 manual.brand；version/effective_date 從 manual 取不到，留 None。
    TODO: manuals 表增 version + effective_date 欄位後更新。
    """
    return {
        "id": manual["id"],
        "doc_type": "manual",
        "title": manual.get("title", ""),
        "tenant_scope": [],
        "brand_scope": [manual["brand"]] if manual.get("brand") else [],
        "project_scope": [],
        "version": None,
        "effective_date": None,
        "meta": {
            "brand": manual.get("brand"),
            "model": manual.get("model"),
            "file_name": manual.get("file_name"),
            "file_size_bytes": manual.get("file_size_bytes"),
            "status": manual.get("status"),
            "chunk_count": manual.get("chunk_count"),
            "created_at": manual.get("created_at"),
        },
    }


# ---------------------------------------------------------------------------
# GET /kb/documents — listKBDocuments
# ---------------------------------------------------------------------------


@router.get(
    "/kb/documents",
    operation_id="listKBDocuments",
    summary="KB 文件列表 v2（tenant-scoped, doc_type 分派, ADR-0101 §2.3）",
    tags=["KB (Agent Knowledge Base)"],
)
async def list_kb_documents(
    doc_type: str | None = Query(default=None, description="文件類型過濾：case / manual"),
    brand: str | None = Query(default=None, description="品牌過濾（對映 brand_scope）"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """GET /kb/documents — 依 doc_type 分派到 case_service / manual_service。

    doc_type 未給時同時查 case + manual，合併後回傳（分頁為各自 limit/2 再合併）。
    """
    if doc_type and doc_type not in _DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type must be one of: {', '.join(sorted(_DOC_TYPES))}",
            422,
        )

    tenant_id = user.tenant_id
    items: list[dict] = []
    next_cursor: str | None = None
    has_more = False

    if doc_type == "case" or doc_type is None:
        sub_limit = limit if doc_type else max(1, limit // 2)
        case_page = await case_service.list_cases(
            tenant_id=tenant_id,
            cursor=cursor if doc_type == "case" else None,
            limit=sub_limit,
            brand=brand,
            verified=None,
        )
        for c in case_page["items"]:
            items.append(_case_to_kb_document(c))
        if doc_type == "case":
            next_cursor = case_page["next_cursor"]
            has_more = case_page["has_more"]

    if doc_type == "manual" or doc_type is None:
        sub_limit = limit if doc_type else max(1, limit - len(items))
        manual_page = await manual_service.list_manuals(
            tenant_id=tenant_id,
            cursor=cursor if doc_type == "manual" else None,
            limit=sub_limit,
            brand=brand,
        )
        for m in manual_page["items"]:
            items.append(_manual_to_kb_document(m))
        if doc_type == "manual":
            next_cursor = manual_page["next_cursor"]
            has_more = manual_page["has_more"]

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


# ---------------------------------------------------------------------------
# POST /kb/documents — ingestKBDocument
# ---------------------------------------------------------------------------


@router.post(
    "/kb/documents",
    operation_id="ingestKBDocument",
    summary="KB 文件建立 v2（doc_type=case/manual, Idempotency-Key, ADR-0101 §2.3）",
    status_code=status.HTTP_201_CREATED,
    tags=["KB (Agent Knowledge Base)"],
)
async def ingest_kb_document(
    body: dict[str, Any],
    user: CurrentUser = Depends(require_tenant),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    """POST /kb/documents — 依 body.doc_type 分派建立。

    doc_type=case：呼叫 case_service.create_case
      必填 body 欄位：doc_type, title, brand, problem_description, solution
    doc_type=manual：呼叫 manual_service.upload_manual (metadata-only, 無 file bytes)
      必填 body 欄位：doc_type, title, brand, source_uri (作為 file_name fallback)
      注意：此路徑不上傳 PDF 內容；完整 PDF 上傳仍走
            /api/v1/knowledge-base/manuals/upload（multipart form）。
    """
    doc_type = body.get("doc_type")
    if not doc_type or doc_type not in _DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type is required and must be one of: {', '.join(sorted(_DOC_TYPES))}",
            422,
        )

    tenant_id = user.tenant_id
    payload_out: dict

    if doc_type == "case":
        # 必填驗證
        for field in ("title", "brand", "problem_description", "solution"):
            if not body.get(field):
                raise ApiError("VALIDATION_ERROR", f"{field} is required for doc_type=case", 422)
        case = await case_service.create_case(
            tenant_id=tenant_id,
            payload={
                "title": body["title"],
                "brand": body["brand"],
                "problem_description": body["problem_description"],
                "solution": body["solution"],
                "model": body.get("model"),
                "tags": body.get("tags") or [],
            },
            created_by=user.user_id,
        )
        payload_out = _case_to_kb_document(case)

    else:  # doc_type == "manual"
        # metadata-only 路徑（無 file bytes）
        for field in ("title", "brand"):
            if not body.get(field):
                raise ApiError("VALIDATION_ERROR", f"{field} is required for doc_type=manual", 422)
        source_uri: str = body.get("source_uri") or body.get("title", "unknown")
        # 以 source_uri 作為 filename（只取最後一段）
        filename = source_uri.split("/")[-1] or f"manual-{uuid.uuid4()}.pdf"
        manual = await manual_service.upload_manual(
            tenant_id=tenant_id,
            uploader_user_id=user.user_id,
            filename=filename,
            content_type="application/pdf",
            file_bytes=b"\x00",      # placeholder — pipeline 後續補實際內容
            brand=body["brand"],
            title=body["title"],
            model=body.get("model"),
        )
        payload_out = _manual_to_kb_document(manual)

    if idem is not None:
        await idem.save(201, payload_out)
    return payload_out


# ---------------------------------------------------------------------------
# GET /kb/documents/{docId} — getKBDocument
# ---------------------------------------------------------------------------


@router.get(
    "/kb/documents/{docId}",
    operation_id="getKBDocument",
    summary="KB 文件詳情 v2（scope check, ADR-0101 §2.3）",
    tags=["KB (Agent Knowledge Base)"],
)
async def get_kb_document(
    docId: str = Path(..., description="文件 UUID"),
    doc_type: str | None = Query(
        default=None,
        description=(
            "明確指定文件類型（case / manual）加速查詢；"
            "若未給則先查 case 再查 manual"
        ),
    ),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """GET /kb/documents/{docId} — 先嘗試 case，再嘗試 manual。

    spec 規定 scope check 403；本實作依 tenant_id 隔離（已含 require_tenant），
    若查無文件回 404，其他 tenant 的文件因 tenant 過濾不可見，符合 scope 精神。
    """
    if doc_type and doc_type not in _DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type must be one of: {', '.join(sorted(_DOC_TYPES))}",
            422,
        )

    tenant_id = user.tenant_id

    if doc_type == "case" or doc_type is None:
        try:
            case = await case_service.get_case(tenant_id=tenant_id, case_id=docId)
            return _case_to_kb_document(case)
        except ApiError as e:
            if e.status_code != 404 or doc_type == "case":
                raise

    # doc_type == "manual" or fallthrough from case not found
    try:
        manual_page = await manual_service.list_manuals(
            tenant_id=tenant_id,
            cursor=None,
            limit=1,
            brand=None,
        )
        # list_manuals 無 get_by_id；用 ID 過濾（手動掃）
        # TODO: manual_service 增加 get_manual(tenant_id, manual_id) 以避免 scan
        # 暫以重試 get_case 失敗後的 manual list 搜尋代替
        manual = await _get_manual_by_id(tenant_id=tenant_id, manual_id=docId)
        return _manual_to_kb_document(manual)
    except ApiError:
        raise


async def _get_manual_by_id(*, tenant_id: str, manual_id: str) -> dict:
    """從 manual_service 取單筆 manual（manual_service 僅有 list）。

    TODO: manual_service 目前無 get_by_id；此處以 list 掃描代替，待補後直接呼叫。
    每次最多掃 limit=100 筆，超大 tenant 不適用；僅 MVP 可接受，P3 前需補實作。
    """
    import core.db as db_module
    from core.db import _ensure_conn
    from services.manual_service import _SELECT_COLUMNS, _row_to_dict

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM manuals "
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid AND deleted_at IS NULL",
        (manual_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Document not found", 404)
    return _row_to_dict(row)


# ---------------------------------------------------------------------------
# CR-0005 step 2/3：PUT / DELETE + audit log（HD-02 軟刪 / HD-03 DB 表 audit）
# ---------------------------------------------------------------------------


async def _write_kb_audit_log(
    *,
    tenant_id: str,
    doc_id: str,
    doc_type: str,
    action: str,
    before_state: dict | None,
    after_state: dict | None,
    actor_user_id: str,
    actor_role: str,
) -> None:
    """寫 saas.kb_audit_log（best-effort，失敗不阻擋主操作；CR-0005 HD-03=a）。"""
    try:
        import json as _json
        import core.db as db_module
        from core.db import _ensure_conn

        if not await _ensure_conn():
            return
        await db_module._conn.execute(
            "INSERT INTO saas.kb_audit_log "
            "  (tenant_id, doc_id, doc_type, action, "
            "   before_state, after_state, actor_user_id, actor_role) "
            "VALUES (%s::uuid, %s::uuid, %s, %s, "
            "        %s::jsonb, %s::jsonb, %s::uuid, %s)",
            (
                tenant_id,
                doc_id,
                doc_type,
                action,
                _json.dumps(before_state, ensure_ascii=False) if before_state is not None else None,
                _json.dumps(after_state, ensure_ascii=False) if after_state is not None else None,
                actor_user_id,
                actor_role,
            ),
        )
    except Exception:
        # best-effort：audit log 失敗不阻擋主操作（CR-0005 §10 風險表）
        import logging
        logging.getLogger("kb_v2.audit").warning(
            "kb_audit_log write failed (non-fatal)", exc_info=True
        )


@router.put(
    "/kb/documents/{docId}",
    operation_id="updateKBDocument",
    summary="KB 文件 PUT v2（CR-0005 HD-02 軟刪 / HD-03 audit；doc_type 分派）",
    tags=["KB (Agent Knowledge Base)"],
)
async def update_kb_document(
    body: dict[str, Any],
    docId: str = Path(..., description="文件 UUID"),
    doc_type: str | None = Query(default=None, description="case 或 manual"),
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    if doc_type and doc_type not in _DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type must be one of: {', '.join(sorted(_DOC_TYPES))}",
            422,
        )
    if not isinstance(body, dict):
        raise ApiError("VALIDATION_ERROR", "body must be a JSON object", 422)

    tenant_id = user.tenant_id

    # 先抓 before_state（doc_type 自動 fallback）
    before: dict | None = None
    resolved_type: str | None = doc_type
    if doc_type == "case" or doc_type is None:
        try:
            before = await case_service.get_case(tenant_id=tenant_id, case_id=docId)
            resolved_type = "case"
        except ApiError as e:
            if e.status_code != 404 or doc_type == "case":
                if doc_type == "case":
                    raise
            before = None

    if before is None and (doc_type == "manual" or doc_type is None):
        manual_page = await manual_service.list_manuals(
            tenant_id=tenant_id, cursor=None, limit=100, brand=None,
        )
        before = next((m for m in manual_page.get("items", []) if m.get("id") == docId), None)
        if before:
            resolved_type = "manual"

    if before is None:
        raise ApiError("NOT_FOUND", "Document not found", 404)

    # 執行更新
    after: dict
    if resolved_type == "case":
        after = await case_service.update_case(
            tenant_id=tenant_id, case_id=docId, patch=body,
        )
        kb_doc = _case_to_kb_document(after)
    else:
        # manual update：MVP 僅 title 變更（manual_service 無完整 update；以 audit-only 路徑記）
        raise ApiError(
            "NOT_IMPLEMENTED",
            "manual PUT pending manual_service.update_manual impl",
            501,
        )

    await _write_kb_audit_log(
        tenant_id=tenant_id,
        doc_id=docId,
        doc_type=resolved_type,
        action="update",
        before_state=before,
        after_state=after,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )
    return kb_doc


@router.delete(
    "/kb/documents/{docId}",
    operation_id="deleteKBDocument",
    summary="KB 文件 DELETE v2（CR-0005 HD-02 軟刪 deleted_at / HD-03 audit）",
    status_code=204,
    tags=["KB (Agent Knowledge Base)"],
)
async def delete_kb_document(
    docId: str = Path(..., description="文件 UUID"),
    doc_type: str | None = Query(default=None, description="case 或 manual"),
    user: CurrentUser = Depends(require_tenant),
) -> None:
    if doc_type and doc_type not in _DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type must be one of: {', '.join(sorted(_DOC_TYPES))}",
            422,
        )

    tenant_id = user.tenant_id

    # before snapshot for audit
    before: dict | None = None
    resolved_type: str | None = doc_type
    if doc_type == "case" or doc_type is None:
        try:
            before = await case_service.get_case(tenant_id=tenant_id, case_id=docId)
            resolved_type = "case"
        except ApiError as e:
            if e.status_code != 404 or doc_type == "case":
                if doc_type == "case":
                    raise
            before = None

    if before is None and (doc_type == "manual" or doc_type is None):
        manual_page = await manual_service.list_manuals(
            tenant_id=tenant_id, cursor=None, limit=100, brand=None,
        )
        before = next((m for m in manual_page.get("items", []) if m.get("id") == docId), None)
        if before:
            resolved_type = "manual"

    if before is None:
        raise ApiError("NOT_FOUND", "Document not found", 404)

    # 軟刪：標 deleted_at + 既有 is_active（case_entries 沿用）
    if resolved_type == "case":
        import core.db as db_module
        from core.db import _ensure_conn
        if not await _ensure_conn():
            raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
        await db_module._conn.execute(
            "UPDATE case_entries SET is_active = FALSE, deleted_at = NOW(), "
            "  updated_at = NOW() "
            "WHERE id = %s::uuid AND tenant_id = %s::uuid",
            (docId, tenant_id),
        )
    else:
        # manual 改軟刪（既有 delete_manual 是硬刪）；本 endpoint 走軟刪路徑
        import core.db as db_module
        from core.db import _ensure_conn
        if not await _ensure_conn():
            raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
        await db_module._conn.execute(
            "UPDATE manuals SET deleted_at = NOW() "
            "WHERE id = %s::uuid AND tenant_id = %s::uuid",
            (docId, tenant_id),
        )

    await _write_kb_audit_log(
        tenant_id=tenant_id,
        doc_id=docId,
        doc_type=resolved_type,
        action="delete",
        before_state=before,
        after_state=None,
        actor_user_id=user.user_id,
        actor_role=user.role,
    )


# ---------------------------------------------------------------------------
# CR-0005 step 2/3：search（HD-05=a cosine similarity desc）
# ---------------------------------------------------------------------------
#
# 設計取捨：
#   - 業主 HD-05 = cosine similarity desc，理想是 pgvector ORDER BY
#     embedding <=> query_embedding；但需 embedding generation pipeline
#     接 OpenAI/local model，本 commit 範圍外
#   - 既有 case_service.search_cases 用 keyword scoring（已上線）；
#     manual_service 無 search 函式
#   - 折衷：v2 :search 先 wrap case_service.search_cases（keyword path），
#     回傳含 _kb_document meta-wrap shape；query_vector 路徑留 TODO
#   - 結果排序仍以 score desc（keyword 路徑），語義上同 cosine desc 一致


@router.post(
    "/kb/documents:search",
    operation_id="searchKBDocuments",
    summary="KB 文件搜尋 v2（CR-0005 HD-05；MVP keyword scoring，pgvector cosine 路徑待 embedding pipeline）",
    tags=["KB (Agent Knowledge Base)"],
)
async def search_kb_documents(
    body: dict[str, Any],
    user: CurrentUser = Depends(require_tenant),
) -> dict:
    """POST /kb/documents:search — keyword scoring + meta-wrap 響應。

    body：
      - query: str（必填）
      - doc_type: case | manual | null（預設 case；MVP manual 暫不支援搜尋）
      - brand / model: 可選過濾
      - limit: 1-50（預設 5）
      - similarity_threshold: float（case_service 內部使用；UI 通常不傳）
    """
    if not isinstance(body, dict):
        raise ApiError("VALIDATION_ERROR", "body must be a JSON object", 422)

    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ApiError("VALIDATION_ERROR", "query is required (non-empty string)", 422)

    doc_type = body.get("doc_type") or "case"
    if doc_type not in _DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type must be one of: {', '.join(sorted(_DOC_TYPES))}",
            422,
        )

    if doc_type == "manual":
        # MVP：manual 搜尋待 v2 manual_service 補；返回空 hits 不報錯避免 UI 炸
        return {"hits": [], "doc_type": "manual", "_note": "manual search pending impl"}

    raw_limit = body.get("limit", 5)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        raise ApiError("VALIDATION_ERROR", "limit must be integer", 422)
    if not (1 <= limit <= 50):
        raise ApiError("VALIDATION_ERROR", "limit must be 1-50", 422)

    brand = body.get("brand")
    model = body.get("model")
    threshold = body.get("similarity_threshold", 0.75)

    result = await case_service.search_cases(
        tenant_id=user.tenant_id,
        query=query.strip(),
        brand=brand if isinstance(brand, str) else None,
        model=model if isinstance(model, str) else None,
        limit=limit,
        similarity_threshold=float(threshold) if isinstance(threshold, (int, float)) else 0.75,
    )

    # hit 結構：{case: KBDocument(meta-wrap), score}（保留 case wrapper 與 v1 兼容
    # 同時 case 內部走 meta-wrap shape — HD-01=a 對齊）
    hits = result.get("hits", [])
    wrapped = []
    for h in hits:
        case = h.get("case") if isinstance(h, dict) and "case" in h else h
        if not isinstance(case, dict):
            continue
        kb_doc = _case_to_kb_document(case)
        out: dict = {"case": kb_doc}
        if isinstance(h, dict) and "score" in h:
            out["score"] = h["score"]
        wrapped.append(out)

    return {"hits": wrapped, "doc_type": "case"}


# ---------------------------------------------------------------------------
# CR-0005 step 2/3：:export（HD-06=a CSV 為主，JSON 可選 ?format=json）
# ---------------------------------------------------------------------------


@router.post(
    "/kb/documents:export",
    operation_id="exportKBDocuments",
    summary="KB 文件 export v2（CR-0005 HD-06 預設 CSV；?format=json 切換）",
    tags=["KB (Agent Knowledge Base)"],
)
async def export_kb_documents(
    user: CurrentUser = Depends(require_tenant),
    doc_type: str = Query(default="case", description="case 或 manual（manual 暫不支援）"),
    fmt: str = Query(default="csv", alias="format", description="csv 或 json"),
    brand: str | None = Query(default=None),
) -> Any:
    """匯出 KB 文件清單為 CSV（預設）或 JSON。

    MVP scope：case only。limit 內建 10000 上限避免炸 memory。
    """
    if doc_type not in _DOC_TYPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"doc_type must be one of: {', '.join(sorted(_DOC_TYPES))}",
            422,
        )
    if fmt not in {"csv", "json"}:
        raise ApiError("VALIDATION_ERROR", "format must be csv|json", 422)
    if doc_type == "manual":
        raise ApiError(
            "NOT_IMPLEMENTED",
            "manual export pending implementation",
            501,
        )

    tenant_id = user.tenant_id
    EXPORT_MAX = 10000

    # 取 case 全列（依 list_cases 既有過濾邏輯）
    page = await case_service.list_cases(
        tenant_id=tenant_id,
        cursor=None,
        limit=EXPORT_MAX,
        brand=brand,
        verified=None,
    )
    items = page.get("items", [])

    if fmt == "json":
        # JSON 輸出走 meta-wrap shape 與其他 GET 一致
        return {
            "doc_type": "case",
            "count": len(items),
            "items": [_case_to_kb_document(c) for c in items],
        }

    # CSV（預設）
    import csv
    import io
    from fastapi.responses import StreamingResponse

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "title", "brand", "model", "problem_description",
        "solution", "tags", "verified", "embedding_status",
        "created_at", "updated_at",
    ])
    for c in items:
        writer.writerow([
            c.get("id", ""),
            c.get("title", ""),
            c.get("brand", ""),
            c.get("model", "") or "",
            (c.get("problem_description", "") or "").replace("\n", " "),
            (c.get("solution", "") or "").replace("\n", " "),
            ",".join(c.get("tags", []) or []),
            "true" if c.get("verified") else "false",
            c.get("embedding_status", ""),
            c.get("created_at", "") or "",
            c.get("updated_at", "") or "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kb-cases.csv"'},
    )
