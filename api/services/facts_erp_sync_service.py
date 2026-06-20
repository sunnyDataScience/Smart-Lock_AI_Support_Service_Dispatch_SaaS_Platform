"""Facts ↔ ERP 主檔同步（CR-0082 / TI-SYNC-02 / Sync-M02 / ADR-PII-002；mock-first）。

phone/address/device facts 與 ERP customer/site/device 對齊，衝突時 **ERP wins**；
變更寫 audit。reconcile_facts 為純函式（無 DB/LLM/ERP，可單元測）；sync_user_facts 走
SCD2（關舊列 is_current=false + 開新列）+ 一筆 audit。

註：正式 ERP client（真 ERP 主檔 + 憑證）替換 mock ErpClient；agent 側 update_user_info
tool 接線屬白名單變更需 CIA（本服務在 api/ 側不動 CS_TOOL_ALLOWLIST）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import audit_log_service

logger = logging.getLogger("api.facts_erp_sync_service")

# ERP 快照欄位 → user_facts.attr_key
_ERP_ATTR_MAP = {"phone": "phone", "address": "address", "device_id": "device_id"}


@dataclass(frozen=True)
class ErpSnapshot:
    phone: str | None = None
    address: str | None = None
    device_id: str | None = None


@dataclass(frozen=True)
class FactChange:
    attr_key: str
    old_val: str | None
    new_val: str


class ErpClient(Protocol):
    """ERP 主檔讀取介面（mock-first；正式版接真 ERP）。"""
    async def fetch_customer(self, user_id: str) -> ErpSnapshot: ...


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def reconcile_facts(*, erp_snapshot: ErpSnapshot, current_facts: dict[str, str]) -> list[FactChange]:
    """純函式：ERP-wins 衝突解決。回需變更的 FactChange 清單。

    - ERP 值存在且與現有 fact（正規化後）不同 → 一筆 FactChange。
    - ERP 值缺漏（None）→ no-op（不刪現有 fact，避免破壞性同步）。
    """
    changes: list[FactChange] = []
    for erp_field, attr_key in _ERP_ATTR_MAP.items():
        erp_val = getattr(erp_snapshot, erp_field)
        if erp_val is None or not str(erp_val).strip():
            continue  # ERP 缺值 → 不動現有
        cur_val = current_facts.get(attr_key)
        if _normalize(erp_val) != _normalize(cur_val):
            changes.append(FactChange(attr_key=attr_key, old_val=cur_val, new_val=str(erp_val)))
    return changes


async def _load_current_facts(user_id: str) -> dict[str, str]:
    cur = await db_module._conn.execute(
        "SELECT attr_key, attr_val FROM user_facts WHERE user_id = %s AND is_current = true",
        (user_id,))
    return {r[0]: r[1] for r in await cur.fetchall()}


async def sync_user_facts(
    *, user_id: str, erp_snapshot: ErpSnapshot, actor: str = "erp_sync",
) -> dict:
    """SCD2 套用 ERP-wins 變更：關舊列 + 開新列 + 寫一筆 audit。回 {changes, applied}。

    冪等：snapshot 與現有一致 → 0 變更、不寫 audit churn。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _load_current_facts(user_id)
    changes = reconcile_facts(erp_snapshot=erp_snapshot, current_facts=current)
    if not changes:
        return {"changes": [], "applied": 0}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for ch in changes:
        # 關舊 current 列（若有）
        await db_module._conn.execute(
            "UPDATE user_facts SET is_current = false, end_date = %s "
            "WHERE user_id = %s AND attr_key = %s AND is_current = true",
            (now, user_id, ch.attr_key))
        # 開新 current 列
        await db_module._conn.execute(
            "INSERT INTO user_facts (user_id, attr_key, attr_val, is_current, start_date) "
            "VALUES (%s, %s, %s, true, %s)",
            (user_id, ch.attr_key, ch.new_val, now))

    # 一筆 audit（ERP wins 留痕）
    try:
        await audit_log_service.log_event(
            event_type="facts_sync", actor_id=None, actor_role=actor,
            action="facts.erp_sync", target_type="user_facts", target_id=None,
            payload={"user_id": user_id,
                     "changes": [{"attr": c.attr_key, "old": c.old_val, "new": c.new_val}
                                 for c in changes]})
    except Exception as exc:  # noqa: BLE001
        logger.warning("facts_sync audit failed: %s", exc)
    return {"changes": [{"attr": c.attr_key, "old": c.old_val, "new": c.new_val} for c in changes],
            "applied": len(changes)}


async def sync_from_client(*, user_id: str, client: ErpClient, actor: str = "erp_sync") -> dict:
    """從 ERP client 取 snapshot → 同步（正式流程入口；測試注入 fake client）。"""
    snapshot = await client.fetch_customer(user_id)
    return await sync_user_facts(user_id=user_id, erp_snapshot=snapshot, actor=actor)
