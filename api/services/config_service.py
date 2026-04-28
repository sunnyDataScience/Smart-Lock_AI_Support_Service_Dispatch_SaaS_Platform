"""System Config 業務邏輯。單列 per-tenant，PATCH 採 deep-merge。"""

from __future__ import annotations

import json
import logging

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

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
