"""CR-0037 師傅拆帳規則主檔 service（mock-first，仿 CR-0034 catalog）。

esales sheet 21 拆帳草稿（23 服務 × A/B/C 級別 + 夜間/急件加成率）查詢 + 純計算 helper。
base_payout 為內部敏感成本 → include_cost RBAC 遮蔽（同 catalog unit_price）。

UAT-0718 W1-6（業主裁決）：補完整 CRUD（新增/編輯/停用），比照 quote_catalog（CR-0110）
軟刪模式（deleted_at，migration 109）；拆帳牽師傅佣金 → 每次寫入硬性記 audit_events
（before/after 快照；稽核寫入失敗即整筆回滾，不 best-effort 吞掉）。

NOT wired：reconciliation 拆帳重算（目前硬編 80% / ADR-0041）改查表 → Phase II
（需 work_orders 夜間/急件旗標 + 業主 Q-09 確認）。
"""

from __future__ import annotations

from datetime import date
from typing import Any

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services import audit_log_service


def _dec(v) -> str | None:
    return None if v is None else f"{float(v):.2f}"


async def _conn():
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


def _row_to_dict(r: tuple, include_cost: bool) -> dict:
    out = {
        "rule_id": r[0], "service_code": r[1], "service_name": r[2], "level_id": r[3],
        "night_surcharge_pct": float(r[5]), "urgent_surcharge_pct": float(r[6]),
        "currency": r[7],
        "effective_date": r[8].isoformat() if r[8] else None,
        "expiry_date": r[9].isoformat() if r[9] else None,
        "decision_status": r[10], "is_mock": bool(r[11]),
    }
    if include_cost:
        out["base_payout"] = _dec(r[4])  # 內部敏感：僅 admin/ops 可見
    return out


_SELECT = ("rule_id, service_code, service_name, level_id, base_payout, night_surcharge_pct, "
           "urgent_surcharge_pct, currency, effective_date, expiry_date, decision_status, is_mock")


async def list_rules(*, tenant_id: str | None, include_cost: bool,
                     service_code: str | None = None) -> list[dict]:
    """列拆帳規則；base_payout 依 include_cost RBAC 遮蔽。

    租戶隔離（仿 CR-0034 catalog）：回全域（tenant_id IS NULL，目前 seed 皆全域共享）
    + 該租戶自訂規則（未來）。靜態 WHERE + 參數化避免動態拼接。軟刪列不列出（W1-6）。
    """
    conn = await _conn()
    rows = await (await conn.execute(
        f"SELECT {_SELECT} FROM technician_payout_rule "
        "WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) AND deleted_at IS NULL "
        "  AND (%s::text IS NULL OR service_code = %s) "
        "ORDER BY service_code, level_id",
        (tenant_id, service_code, service_code))).fetchall()
    return [_row_to_dict(r, include_cost) for r in rows]


async def get_rule(*, tenant_id: str | None, service_code: str, level_id: str,
                   on_date: date | None = None, include_cost: bool = False) -> dict | None:
    """取單一 service×level 的生效拆帳規則（effective_date ≤ on_date 且未過期）。

    多版本時取最新生效（ORDER BY effective_date DESC NULLS LAST LIMIT 1）；無對應 → None。
    base_payout / base_payout_raw（內部成本）僅在 include_cost=True 才回（預設 False 防外洩）；
    Phase II reconciliation 重算內部呼叫時帶 include_cost=True。租戶隔離同 list_rules。
    """
    conn = await _conn()
    d = on_date or date.today()
    r = await (await conn.execute(
        f"SELECT {_SELECT} FROM technician_payout_rule "
        "WHERE (tenant_id IS NULL OR tenant_id = %s::uuid) AND deleted_at IS NULL "
        "  AND service_code = %s AND level_id = %s "
        "  AND (effective_date IS NULL OR effective_date <= %s) "
        "  AND (expiry_date IS NULL OR expiry_date > %s) "
        "ORDER BY effective_date DESC NULLS LAST LIMIT 1",
        (tenant_id, service_code, level_id, d, d))).fetchone()
    if not r:
        return None
    out = _row_to_dict(r, include_cost=include_cost)
    if include_cost:
        out["base_payout_raw"] = float(r[4])
    return out


def compute_payout(*, base_payout: float, night: bool = False, urgent: bool = False,
                   night_pct: float = 0.0, urgent_pct: float = 0.0) -> float:
    """純計算拆帳金額（CR-0037）：base × (1+夜間?) × (1+急件?)。

    純函式，不查 DB；reconciliation 重算接此（Phase II）。加成乘法疊加（與 base 一致幣別）。
    """
    amount = float(base_payout)
    if night:
        amount *= (1 + float(night_pct))
    if urgent:
        amount *= (1 + float(urgent_pct))
    return round(amount, 2)


# ─────────────────────────────────────────────────────────────────────────────
# CRUD（UAT-0718 W1-6 業主裁決）— 比照 quote_catalog（CR-0110）：
#   - create：rule_id 唯一（未刪列），重複 → 409 CODE_TAKEN；寫入 tenant_id +
#     is_mock=FALSE + decision_status='accepted'（租戶自填即正式值，前端映「已確認」）
#   - update：白名單欄位 partial update；同樣翻 is_mock/decision_status
#   - delete：軟刪/停用 SET deleted_at=NOW()（可復原、月結重算價來源可稽核）
#   - 審計硬性：拆帳牽師傅佣金——每次寫入在同一交易記 audit_events
#     （actor/action/before/after），稽核寫不進就整筆回滾（同 UAT-0718 R1 原則）
# ─────────────────────────────────────────────────────────────────────────────

# 租戶自行維護後的確認狀態（值域對齊 migration 045/082：draft/draft_review/accepted）
_CONFIRMED_STATUS = "accepted"

# 可寫欄位白名單（rule_id 由 create 專屬處理）
_RULE_FIELDS = ("service_code", "service_name", "level_id", "base_payout",
                "night_surcharge_pct", "urgent_surcharge_pct", "currency",
                "effective_date", "expiry_date")
_RULE_REQUIRED = ("service_code", "level_id", "base_payout")
_MAX_LEN = {"service_code": 40, "service_name": 120, "level_id": 10, "currency": 8}


def _parse_iso_date(field: str, v: Any) -> date:
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ApiError("VALIDATION_ERROR", f"{field} 必須為 ISO 日期（YYYY-MM-DD）", 422)


def _validate_rule_fields(data: dict[str, Any], *, require_all: bool) -> dict[str, Any]:
    """白名單過濾 + 必填/數值/比例/日期驗證。回可寫入的欄位 dict。

    - base_payout ≥ 0（內部拆帳成本不可為負）
    - night/urgent_surcharge_pct 為比例 0~1（非百分比整數）
    - effective_date/expiry_date ISO 日期；跨欄 effective ≤ expiry 由呼叫端以合併值檢查
    """
    out: dict[str, Any] = {}
    for f in _RULE_FIELDS:
        if f not in data or data[f] is None:
            continue
        v = data[f]
        if f == "base_payout":
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise ApiError("VALIDATION_ERROR", "base_payout 必須為數字", 422)
            if v < 0:
                raise ApiError("VALIDATION_ERROR", "base_payout 不可為負數", 422)
        elif f in ("night_surcharge_pct", "urgent_surcharge_pct"):
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise ApiError("VALIDATION_ERROR", f"{f} 必須為數字", 422)
            if not (0 <= v <= 1):
                raise ApiError("VALIDATION_ERROR", f"{f} 必須為 0~1 之間的比例（例 0.2 = 20%）", 422)
        elif f in ("effective_date", "expiry_date"):
            v = _parse_iso_date(f, v)
        elif isinstance(v, str):
            v = v.strip()
            if not v:
                continue
            if f in _MAX_LEN and len(v) > _MAX_LEN[f]:
                raise ApiError("VALIDATION_ERROR", f"{f} 長度上限 {_MAX_LEN[f]}", 422)
        out[f] = v
    if require_all:
        for f in _RULE_REQUIRED:
            if out.get(f) is None:
                raise ApiError("VALIDATION_ERROR", f"{f} 為必填", 422)
    return out


def _check_date_order(effective: Any, expiry: Any) -> None:
    if effective is not None and expiry is not None and effective > expiry:
        raise ApiError("VALIDATION_ERROR", "effective_date 不可晚於 expiry_date", 422)


def _snapshot(row: tuple | None) -> dict | None:
    """audit before/after 快照（JSON 可序列化；含內部 base_payout——audit 僅後台可讀）。"""
    if row is None:
        return None
    keys = ("rule_id", "service_code", "service_name", "level_id", "base_payout",
            "night_surcharge_pct", "urgent_surcharge_pct", "currency",
            "effective_date", "expiry_date", "decision_status", "is_mock")
    out: dict[str, Any] = {}
    for k, v in zip(keys, row):
        if isinstance(v, date):
            v = v.isoformat()
        elif k in ("base_payout", "night_surcharge_pct", "urgent_surcharge_pct") and v is not None:
            v = float(v)
        out[k] = v
    return out


async def _fetch_snapshot(rule_id: str, tenant_id: str) -> dict | None:
    conn = await _conn()
    r = await (await conn.execute(
        f"SELECT {_SELECT} FROM technician_payout_rule "
        "WHERE rule_id = %s AND deleted_at IS NULL "
        "  AND (tenant_id IS NULL OR tenant_id = %s::uuid)",
        (rule_id, tenant_id))).fetchone()
    return _snapshot(r)


async def _hard_audit(*, action: str, actor_id: str | None, actor_role: str | None,
                      rule_id: str, before: dict | None, after: dict | None) -> None:
    """稽核硬性寫入：失敗即 raise（外層交易回滾整筆操作，不留無稽核的寫入）。

    audit_events.target_id 為 UUID 欄，rule_id 是文字主鍵 → 放 payload 追溯。
    """
    await audit_log_service.log_event_returning_id(
        event_type="financial_action",
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target_type="technician_payout_rule",
        payload={"rule_id": rule_id, "before": before, "after": after},
    )


async def create_rule(*, tenant_id: str, actor_id: str | None, actor_role: str | None,
                      rule_id: str, data: dict[str, Any]) -> dict:
    """新增拆帳規則。rule_id 唯一（未刪列）；寫入即租戶確認值 + 硬性稽核。"""
    conn = await _conn()
    rule_id = (rule_id or "").strip()
    if not rule_id or len(rule_id) > 60:
        raise ApiError("VALIDATION_ERROR", "rule_id 為必填且長度 ≤ 60", 422)
    fields = _validate_rule_fields(data, require_all=True)
    _check_date_order(fields.get("effective_date"), fields.get("expiry_date"))

    dup = await (await conn.execute(
        "SELECT 1 FROM technician_payout_rule WHERE rule_id = %s AND deleted_at IS NULL",
        (rule_id,))).fetchone()
    if dup:
        raise ApiError("CODE_TAKEN", f"規則代碼 {rule_id} 已存在", 409)

    after = {**{k: (v.isoformat() if isinstance(v, date) else v) for k, v in fields.items()},
             "rule_id": rule_id, "decision_status": _CONFIRMED_STATUS, "is_mock": False}
    try:
        async with conn.transaction():
            # rule_id 是物理 PK，軟刪列仍佔用 → 對已刪同 code 走「復活」覆寫，否則 INSERT
            revived = await conn.execute(
                "UPDATE technician_payout_rule SET deleted_at = NULL, tenant_id = %s::uuid, "
                "  is_mock = FALSE, decision_status = %s, updated_at = NOW(), "
                f"  {', '.join(f'{f} = %s' for f in fields)} "
                "WHERE rule_id = %s AND deleted_at IS NOT NULL "
                "RETURNING rule_id",
                (tenant_id, _CONFIRMED_STATUS, *fields.values(), rule_id),
            )
            if not await revived.fetchone():
                cols = ["rule_id", "tenant_id", "is_mock", "decision_status", *fields.keys()]
                placeholders = ["%s", "%s::uuid", "%s", "%s", *["%s"] * len(fields)]
                await conn.execute(
                    f"INSERT INTO technician_payout_rule ({', '.join(cols)}) "
                    f"VALUES ({', '.join(placeholders)})",
                    (rule_id, tenant_id, False, _CONFIRMED_STATUS, *fields.values()),
                )
            await _hard_audit(action="payout_rule.created", actor_id=actor_id,
                              actor_role=actor_role, rule_id=rule_id, before=None, after=after)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 — 稽核/寫入失敗整筆回滾（W1-6 硬性）
        raise ApiError("AUDIT_WRITE_FAILED",
                       "拆帳規則寫入或稽核失敗，操作已回滾（稽核為硬性要求）", 500) from exc
    return {"rule_id": rule_id}


async def update_rule(*, tenant_id: str, actor_id: str | None, actor_role: str | None,
                      rule_id: str, data: dict[str, Any]) -> dict:
    """編輯拆帳規則（partial）。任何編輯視為租戶確認 → is_mock=FALSE + accepted；硬性稽核。"""
    conn = await _conn()
    fields = _validate_rule_fields(data, require_all=False)
    if not fields:
        raise ApiError("VALIDATION_ERROR", "沒有可更新的欄位", 422)

    before = await _fetch_snapshot(rule_id, tenant_id)
    if before is None:
        raise ApiError("NOT_FOUND", f"找不到規則代碼 {rule_id}", 404)

    # 跨欄日期檢查以「合併後」值為準（只改其中一欄也不可造成 effective > expiry）
    eff = fields.get("effective_date",
                     _parse_iso_date("effective_date", before["effective_date"])
                     if before["effective_date"] else None)
    exp = fields.get("expiry_date",
                     _parse_iso_date("expiry_date", before["expiry_date"])
                     if before["expiry_date"] else None)
    _check_date_order(eff, exp)

    sets = [f"{f} = %s" for f in fields]
    sets += ["is_mock = FALSE", "decision_status = %s", "updated_at = NOW()"]
    try:
        async with conn.transaction():
            cur = await conn.execute(
                f"UPDATE technician_payout_rule SET {', '.join(sets)} "
                "WHERE rule_id = %s AND deleted_at IS NULL "
                "  AND (tenant_id IS NULL OR tenant_id = %s::uuid) "
                "RETURNING rule_id",
                (*fields.values(), _CONFIRMED_STATUS, rule_id, tenant_id),
            )
            if not await cur.fetchone():
                raise ApiError("NOT_FOUND", f"找不到規則代碼 {rule_id}", 404)
            after = {**before,
                     **{k: (v.isoformat() if isinstance(v, date) else v) for k, v in fields.items()},
                     "decision_status": _CONFIRMED_STATUS, "is_mock": False}
            await _hard_audit(action="payout_rule.updated", actor_id=actor_id,
                              actor_role=actor_role, rule_id=rule_id, before=before, after=after)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ApiError("AUDIT_WRITE_FAILED",
                       "拆帳規則寫入或稽核失敗，操作已回滾（稽核為硬性要求）", 500) from exc
    return {"rule_id": rule_id}


async def delete_rule(*, tenant_id: str, actor_id: str | None, actor_role: str | None,
                      rule_id: str) -> dict:
    """停用拆帳規則（軟刪 deleted_at=NOW()；月結價來源可追溯，可人工復原）；硬性稽核。"""
    conn = await _conn()
    before = await _fetch_snapshot(rule_id, tenant_id)
    if before is None:
        raise ApiError("NOT_FOUND", f"找不到規則代碼 {rule_id}", 404)
    try:
        async with conn.transaction():
            cur = await conn.execute(
                "UPDATE technician_payout_rule SET deleted_at = NOW(), updated_at = NOW() "
                "WHERE rule_id = %s AND deleted_at IS NULL "
                "  AND (tenant_id IS NULL OR tenant_id = %s::uuid) "
                "RETURNING rule_id",
                (rule_id, tenant_id),
            )
            if not await cur.fetchone():
                raise ApiError("NOT_FOUND", f"找不到規則代碼 {rule_id}", 404)
            await _hard_audit(action="payout_rule.deleted", actor_id=actor_id,
                              actor_role=actor_role, rule_id=rule_id, before=before, after=None)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ApiError("AUDIT_WRITE_FAILED",
                       "拆帳規則寫入或稽核失敗，操作已回滾（稽核為硬性要求）", 500) from exc
    return {"rule_id": rule_id}
