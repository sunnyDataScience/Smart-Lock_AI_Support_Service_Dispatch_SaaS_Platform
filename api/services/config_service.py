"""System Config 業務邏輯。單列 per-tenant，PATCH 採 deep-merge。"""

from __future__ import annotations

import json
import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services.cancellation_service import DEFAULT_CANCELLATION_CONFIG
from services.warranty_service import DEFAULT_WARRANTY_CONFIG

logger = logging.getLogger("api.config_service")

DEFAULT_CONFIG: dict = {
    "rag": {
        "similarity_threshold": 0.85,
        "max_results": 3,
        "chunk_size": 800,
        "chunk_overlap": 100,
    },
    "llm": {
        "model": "vertex_ai/gemini-2.5-pro",
        "temperature": 0.2,
        "max_tokens": 1024,
        "system_prompt_version": "v1.0",
    },
    # M18 cancellation namespace (ADR-0102 §E / ADR-0067) — 取消費/reason code/累犯閾值
    "cancellation": DEFAULT_CANCELLATION_CONFIG,
    # M13 warranty namespace (ADR-0044 v2 / FR-0015) — 5-mode 起算 / period / B2B override
    "warranty": DEFAULT_WARRANTY_CONFIG,
    "resolution": {
        "faq_confidence_threshold": 0.7,
        "rag_confidence_threshold": 0.6,
        "auto_escalation_enabled": True,
    },
    "line_bot": {
        "greeting_message_enabled": True,
        "max_conversation_turns": 30,
    },
}


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        if v is None:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


async def get_config(tenant_id: str) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT config FROM system_config WHERE tenant_id = %s::uuid",
        (tenant_id,),
    )
    row = await cur.fetchone()
    if not row:
        # 第一次取 → 初始化預設值
        await db_module._conn.execute(
            "INSERT INTO system_config (tenant_id, config) VALUES (%s::uuid, %s::jsonb) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant_id, json.dumps(DEFAULT_CONFIG)),
        )
        return DEFAULT_CONFIG
    return row[0]


async def get_cancellation_config(tenant_id: str) -> tuple[dict, str]:
    """取 cancellation namespace 設定 + config version snapshot（ADR-0067 §5）。

    回 (cancellation_config, config_version_str)。tenant 尚無 config row 時用預設值，
    version 標 'default'。version 用於寫入 cancellation.config_version_used。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT config, version FROM system_config WHERE tenant_id = %s::uuid",
        (tenant_id,),
    )
    row = await cur.fetchone()
    if not row:
        return (DEFAULT_CANCELLATION_CONFIG, "default")
    config = row[0] or {}
    version = str(row[1]) if row[1] is not None else "1"
    cancellation = config.get("cancellation") or DEFAULT_CANCELLATION_CONFIG
    return (cancellation, version)


async def update_config(tenant_id: str, patch: dict, *, updated_by: str | None) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await get_config(tenant_id)
    merged = _deep_merge(current, patch)

    await db_module._conn.execute(
        "INSERT INTO system_config (tenant_id, config, version, updated_by) "
        "VALUES (%s::uuid, %s::jsonb, 1, %s::uuid) "
        "ON CONFLICT (tenant_id) DO UPDATE "
        "SET config = EXCLUDED.config, "
        "    version = system_config.version + 1, "
        "    updated_by = EXCLUDED.updated_by, "
        "    updated_at = CURRENT_TIMESTAMP",
        (tenant_id, json.dumps(merged), updated_by),
    )
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Warranty namespace（ADR-0044 v2 / FR-0015）— 照 get_cancellation_config 寫法
# append-only，避免與平行分支衝突。
# ─────────────────────────────────────────────────────────────────────────────

async def get_warranty_config(tenant_id: str) -> tuple[dict, str]:
    """取 warranty namespace 設定 + config version snapshot。

    回 (warranty_config, config_version_str)。tenant 尚無 config row 時用預設值，
    version 標 'default'。version 用於寫入 warranty 起算 audit 的 config snapshot。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT config, version FROM system_config WHERE tenant_id = %s::uuid",
        (tenant_id,),
    )
    row = await cur.fetchone()
    if not row:
        return (DEFAULT_WARRANTY_CONFIG, "default")
    config = row[0] or {}
    version = str(row[1]) if row[1] is not None else "1"
    warranty = config.get("warranty") or DEFAULT_WARRANTY_CONFIG
    return (warranty, version)
