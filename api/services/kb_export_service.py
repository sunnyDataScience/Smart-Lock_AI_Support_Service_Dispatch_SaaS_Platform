"""KB 向量索引匯出 — 同步生成 JSONL 並以 in-process job store 暫存。

operationId 對齊 openapi.yaml：startKbExport / getKbExport（+ 內部 download 路徑）

設計：
  - 不接 message queue / worker，啟動即同步生成 → status='completed'
  - job 結果儲存在 process 內的 _JOBS dict，以 job_id 為 key
  - 同 process 多請求共享；重啟後遺失（前端拿到的 job_id 在重啟後 404）
  - tenant 隔離：job 物件記錄 tenant_id，read 時比對

scope 過濾：
  - all          → 案例 + 手冊
  - cases_only   → 僅案例
  - manuals_only → 僅手冊

brand 過濾：精確比對 case_entries.brand / manuals.brand（NULL 不命中）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.kb_export_service")


_VALID_SCOPES = {"all", "cases_only", "manuals_only"}

# In-process job store: job_id → job dict
# job dict: {job_id, tenant_id, status, content (bytes), item_count,
#            scope, brand, created_at, completed_at}
_JOBS: dict[str, dict] = {}
_MAX_JOBS = 50  # 軟上限，超過時 evict 最舊（同 process FIFO）


def _evict_if_needed() -> None:
    if len(_JOBS) <= _MAX_JOBS:
        return
    # FIFO evict
    oldest = sorted(_JOBS.items(), key=lambda kv: kv[1].get("created_at") or datetime.min)
    for jid, _ in oldest[: len(_JOBS) - _MAX_JOBS]:
        _JOBS.pop(jid, None)


async def _fetch_cases(tenant_id: str, brand: str | None) -> list[dict]:
    where = ["tenant_id = %s::uuid", "is_active = TRUE"]
    args: list = [tenant_id]
    if brand:
        where.append("brand = %s")
        args.append(brand)
    sql = (
        "SELECT id, title, problem_description, solution, brand, model, "
        "       lock_type, difficulty, tags, verified, embedding_status, "
        "       hit_count, created_at, updated_at "
        "FROM case_entries "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC"
    )
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()
    return [
        {
            "type": "case",
            "id": str(r[0]),
            "title": r[1],
            "problem_description": r[2],
            "solution": r[3],
            "brand": r[4],
            "model": r[5],
            "lock_type": r[6],
            "difficulty": r[7],
            "tags": list(r[8] or []),
            "verified": bool(r[9]),
            "embedding_status": r[10],
            "hit_count": r[11] or 0,
            "created_at": r[12].isoformat() if r[12] else None,
            "updated_at": r[13].isoformat() if r[13] else None,
        }
        for r in rows
    ]


async def _fetch_manuals(tenant_id: str, brand: str | None) -> list[dict]:
    where = ["tenant_id = %s::uuid"]
    args: list = [tenant_id]
    if brand:
        where.append("brand = %s")
        args.append(brand)
    sql = (
        "SELECT id, filename, title, brand, model, total_pages, total_chunks, "
        "       status, file_size_bytes, created_at "
        "FROM manuals "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY created_at DESC"
    )
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()
    return [
        {
            "type": "manual",
            "id": str(r[0]),
            "filename": r[1],
            "title": r[2],
            "brand": r[3],
            "model": r[4],
            "total_pages": r[5],
            "total_chunks": r[6] or 0,
            "status": r[7],
            "file_size_bytes": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]


def _serialize_jsonl(items: list[dict]) -> bytes:
    return ("\n".join(
        json.dumps(item, ensure_ascii=False) for item in items
    ) + ("\n" if items else "")).encode("utf-8")


async def start_export(
    *, tenant_id: str, scope: str = "all", brand: str | None = None,
) -> dict:
    """同步生成匯出檔，立即回傳 status='completed' 的 job 物件。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if scope not in _VALID_SCOPES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"scope must be one of {sorted(_VALID_SCOPES)}",
            422,
        )

    items: list[dict] = []
    if scope in ("all", "cases_only"):
        items.extend(await _fetch_cases(tenant_id, brand))
    if scope in ("all", "manuals_only"):
        items.extend(await _fetch_manuals(tenant_id, brand))

    content = _serialize_jsonl(items)
    now = datetime.now(timezone.utc)
    job_id = str(uuid4())

    job = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "status": "completed",
        "content": content,
        "item_count": len(items),
        "scope": scope,
        "brand": brand,
        "created_at": now,
        "completed_at": now,
    }
    _JOBS[job_id] = job
    _evict_if_needed()
    return job


def _job_to_response(job: dict, *, base_url: str | None = None) -> dict:
    download_url = None
    if job.get("status") == "completed" and base_url:
        download_url = f"{base_url.rstrip('/')}/api/v1/knowledge-base/export/{job['job_id']}/download"
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "download_url": download_url,
        "item_count": job.get("item_count"),
        "created_at": job["created_at"].isoformat() if isinstance(job.get("created_at"), datetime) else job.get("created_at"),
        "completed_at": (
            job["completed_at"].isoformat()
            if isinstance(job.get("completed_at"), datetime)
            else job.get("completed_at")
        ),
    }


async def get_export(*, tenant_id: str, job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if not job or job.get("tenant_id") != tenant_id:
        raise ApiError("NOT_FOUND", "Export job not found", 404)
    return job


async def download_export(*, tenant_id: str, job_id: str) -> tuple[bytes, str]:
    job = await get_export(tenant_id=tenant_id, job_id=job_id)
    if job.get("status") != "completed":
        raise ApiError(
            "STATE_CONFLICT",
            f"Export job is not yet completed (status={job.get('status')})",
            409,
        )
    filename = f"kb-export-{job_id[:8]}.jsonl"
    return job["content"], filename
