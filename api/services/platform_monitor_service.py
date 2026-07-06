"""平台維運監控服務(CR-0116)。

「一品牌一 GCP 專案」部署下,用 GCP Console 一家一家看 container 狀態不可行
(>10 視窗上限)。此服務管理監控目標 registry(monitor_target,平台庫)+ 對所有
啟用目標**並發探測** /health,回即時狀態供 console「維運監控」分頁畫紅綠燈。

定位切割(CR-0116 §1):console 只做**即時紅綠燈**;深度指標/告警/歷史走 GCP
原生(Metrics Scope + Uptime Check + Alerting)。故此服務**不存狀態歷史**——
探測結果即時回傳,不落庫(§8-Q3 裁決 a)。

探測預算(§8-Q7):單目標逾時 3s、並發(非序列)、狀態映射
200→up / 503→degraded / 其他或逾時→down。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import aiohttp

import core.db as db_module
from core.errors import ApiError

logger = logging.getLogger("api.platform_monitor")

#: 單目標探測逾時(秒)。慢/掛的目標逾時即標 down,不 block 整頁。
_PROBE_TIMEOUT_S = 3.0

_SELECT_COLS = "id, brand, label, url, enabled, sort_order, note, created_at, updated_at"


async def _conn():
    try:
        return await db_module.require_platform_conn()
    except RuntimeError:
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)


def _row_to_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "brand": row[1],
        "label": row[2],
        "url": row[3],
        "enabled": row[4],
        "sort_order": row[5],
        "note": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
        "updated_at": row[8].isoformat() if row[8] else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Registry CRUD
# ─────────────────────────────────────────────────────────────────────────────

def _validate(brand: str, label: str, url: str) -> tuple[str, str, str]:
    b, la, u = (brand or "").strip(), (label or "").strip(), (url or "").strip()
    if not b or not la or not u:
        raise ApiError("VALIDATION_ERROR", "brand、label、url 皆為必填", 422)
    if not (u.startswith("http://") or u.startswith("https://")):
        raise ApiError("VALIDATION_ERROR", "url 必須以 http:// 或 https:// 開頭", 422)
    if len(u) > 500:
        raise ApiError("VALIDATION_ERROR", "url 過長(上限 500 字元)", 422)
    return b, la, u


async def list_targets() -> dict:
    conn = await _conn()
    cur = await conn.execute(
        f"SELECT {_SELECT_COLS} FROM monitor_target ORDER BY brand, sort_order, label"
    )
    rows = await cur.fetchall()
    return {"data": [_row_to_dict(r) for r in rows], "message": None}


async def create_target(
    *, brand: str, label: str, url: str,
    enabled: bool = True, sort_order: int = 0, note: str | None = None,
) -> dict:
    b, la, u = _validate(brand, label, url)
    conn = await _conn()
    cur = await conn.execute(
        "INSERT INTO monitor_target (brand, label, url, enabled, sort_order, note) "
        f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {_SELECT_COLS}",
        (b, la, u, enabled, sort_order, (note or "").strip() or None),
    )
    row = await cur.fetchone()
    logger.info("monitor_target 新增 brand=%s label=%s", b, la)
    return {"data": _row_to_dict(row), "message": None}


async def update_target(*, target_id: str, patch: dict) -> dict:
    sets: list[str] = []
    args: list = []
    if "brand" in patch or "label" in patch or "url" in patch:
        # 任一核心欄位變動 → 一併驗證(取現值填補未提供者)
        conn0 = await _conn()
        cur0 = await conn0.execute(
            "SELECT brand, label, url FROM monitor_target WHERE id = %s::uuid", (target_id,)
        )
        cur_row = await cur0.fetchone()
        if not cur_row:
            raise ApiError("NOT_FOUND", "監控目標不存在", 404)
        b, la, u = _validate(
            patch.get("brand", cur_row[0]),
            patch.get("label", cur_row[1]),
            patch.get("url", cur_row[2]),
        )
        sets += ["brand = %s", "label = %s", "url = %s"]
        args += [b, la, u]
    if "enabled" in patch:
        sets.append("enabled = %s")
        args.append(bool(patch["enabled"]))
    if "sort_order" in patch:
        sets.append("sort_order = %s")
        args.append(int(patch["sort_order"]))
    if "note" in patch:
        sets.append("note = %s")
        args.append((patch.get("note") or "").strip() or None)
    if not sets:
        raise ApiError("VALIDATION_ERROR", "無可更新欄位", 422)
    sets.append("updated_at = CURRENT_TIMESTAMP")
    args.append(target_id)
    conn = await _conn()
    cur = await conn.execute(
        f"UPDATE monitor_target SET {', '.join(sets)} WHERE id = %s::uuid RETURNING {_SELECT_COLS}",
        tuple(args),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "監控目標不存在", 404)
    return {"data": _row_to_dict(row), "message": None}


async def delete_target(*, target_id: str) -> None:
    conn = await _conn()
    cur = await conn.execute(
        "DELETE FROM monitor_target WHERE id = %s::uuid RETURNING id", (target_id,)
    )
    if not await cur.fetchone():
        raise ApiError("NOT_FOUND", "監控目標不存在", 404)


# ─────────────────────────────────────────────────────────────────────────────
# 並發健康探測(不落庫;即時回傳)
# ─────────────────────────────────────────────────────────────────────────────

def _map_status(http_code: int | None) -> str:
    """/health 200→up、503→degraded(DB 降級)、其他/逾時→down。"""
    if http_code == 200:
        return "up"
    if http_code == 503:
        return "degraded"
    return "down"


async def _probe_one(session: aiohttp.ClientSession, target: dict) -> dict:
    started = time.monotonic()
    http_code: int | None = None
    error: str | None = None
    try:
        async with session.get(
            target["url"], timeout=aiohttp.ClientTimeout(total=_PROBE_TIMEOUT_S)
        ) as resp:
            http_code = resp.status
            await resp.read()  # 確保連線完成再計時
    except asyncio.TimeoutError:
        error = "timeout"
    except aiohttp.ClientError as e:
        error = type(e).__name__
    except Exception as e:  # noqa: BLE001 — 探測不可讓整批失敗
        error = type(e).__name__
    latency_ms = round((time.monotonic() - started) * 1000)
    return {
        **target,
        "status": _map_status(http_code),
        "http_code": http_code,
        "latency_ms": latency_ms,
        "error": error,
    }


async def probe_health() -> dict:
    """探測所有**啟用**目標的 /health(並發),回即時狀態。不落庫。"""
    conn = await _conn()
    cur = await conn.execute(
        f"SELECT {_SELECT_COLS} FROM monitor_target WHERE enabled = TRUE "
        "ORDER BY brand, sort_order, label"
    )
    rows = await cur.fetchall()
    targets = [_row_to_dict(r) for r in rows]
    checked_at = datetime.now(timezone.utc).isoformat()
    if not targets:
        return {"data": [], "checked_at": checked_at, "message": None}
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[_probe_one(session, t) for t in targets])
    return {"data": list(results), "checked_at": checked_at, "message": None}
