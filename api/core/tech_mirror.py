"""技師身分投影鏡射(CR-0112 方案 B)。

架構:tech DB(TECH_POSTGRES_URI)為技師身分**權威庫**;品牌庫保留技師列
作**投影(mirror)** —— 35 張品牌表(work_orders/dispatch_logs/notifications/
revoked_jti…)FK 指向 users/technicians,投影使 FK 與派工/佣金 JOIN 全不用改。

用法:身分寫入先落權威庫(core.db.require_tech_conn),完成後呼叫本模組把
受影響列以**實際值**(含 DB 端生成的 uuid/timestamp)upsert/刪除到品牌庫,
兩庫不會因各自 DEFAULT 而分岔。

單庫 fallback(TECH_POSTGRES_URI 未設)時全部 no-op —— 權威連線即主連線,
不需要也不能鏡射(會變成同庫重複寫)。

失敗策略:鏡射失敗**大聲失敗**(log ERROR + raise)而非靜默漂移;修復路徑
= `scripts/db/split-tech-db.sh --verify` 查漂移、`--force` 以品牌庫重建基準
或以權威庫覆寫投影(視情況)。
"""

from __future__ import annotations

import logging
from typing import Sequence

from psycopg.types.json import Json

from core import db

logger = logging.getLogger("api.tech_mirror")


def _adapt_row(row: tuple) -> list:
    """SELECT * 取回的 jsonb 欄位是 Python dict/list —— 直接當參數重插會被
    psycopg 適配成 Postgres array(如 {Yale})而非 jsonb → InvalidTextRepresentation。
    以 Json() 包回 jsonb。鏡射表(users/technicians/skill/auth/cert)無原生 array 欄位。"""
    return [Json(v) if isinstance(v, (dict, list)) else v for v in row]

# 允許鏡射的表白名單(避免動態 SQL 被誤用到任意表)
_MIRRORED_TABLES = {
    "users",
    "technicians",
    "technician_skill",
    "technician_brand_authorization",
    "technician_certification",
}

# CR-0164 B：users 投影欄位白名單——**不鏡射 password_hash/email/phone/address 等
# 憑證/PII**（原 SELECT * 全 24 欄鏡射，抵銷 CR-0112「憑證集中權威庫」目的、品牌庫
# 外洩即洩全體技師登入憑證）。品牌側對技師 users 投影的剛性依賴僅：per-request A2/A3
# （is_active/password_changed_at）+ A1 lockout（failed_login_attempts/locked_until）
# + FK 目標（id/tenant_id/role）。技師登入 lookup（email/password_hash 驗證）改讀權威庫
# （auth_service._find_user_by_email/_find_users_by_phone 對 role=['technician'] 路由）。
# 技師顯示名/電話品牌側一律讀 technicians 表非本投影。
_USERS_PROJECTION_COLS = [
    "id", "tenant_id", "role", "is_active",
    "failed_login_attempts", "locked_until", "password_changed_at",
]


# UAT-P1-3(2026-07-18)：權威庫私有欄——不投影到品牌庫。CR-0169 在權威庫
# technicians 加了 LINE 綁定欄(line_user_id/notify_pool_new)，品牌庫投影表
# 沒有(也不該有——綁定資訊隱私最小化)；SELECT * 鏡射把新欄帶進品牌庫
# INSERT → UndefinedColumn 500，炸掉**所有**技師身分寫入路徑(上線切換/
# 排班/資料編輯)。維持其餘欄位缺失大聲失敗(漂移偵測)，僅顯式列出的私有
# 欄跳過。未來在權威庫加「品牌庫不需要」的欄位時，必須同步登記到這裡。
_TECH_PRIVATE_COLS: dict[str, set[str]] = {
    # CR-0169：line_user_id / notify_pool_new；CR-0173：line_user_id_enc /
    # line_user_id_bidx（0724 prod 技師註冊 500 補登記——加密欄同屬綁定隱私，
    # 品牌庫投影不該有，漏登記＝SELECT * 鏡射 UndefinedColumn 炸所有技師身分寫入）。
    "technicians": {
        "line_user_id",
        "notify_pool_new",
        "line_user_id_enc",
        "line_user_id_bidx",
    },
}


def _select_cols(table: str) -> str:
    """鏡射 SELECT 欄位：users 走最小白名單（不含憑證/PII），其餘表全欄。"""
    if table == "users":
        return ", ".join(_USERS_PROJECTION_COLS)
    return "*"


def _drop_private_cols(
    table: str, cols: list[str], rows: list[tuple]
) -> tuple[list[str], list[tuple]]:
    """剔除權威庫私有欄(見 _TECH_PRIVATE_COLS)；無登記則原樣返回。"""
    drop = _TECH_PRIVATE_COLS.get(table)
    if not drop:
        return cols, rows
    keep = [i for i, c in enumerate(cols) if c not in drop]
    return [cols[i] for i in keep], [tuple(row[i] for i in keep) for row in rows]


def _check_table(table: str) -> None:
    if table not in _MIRRORED_TABLES:
        raise ValueError(f"tech_mirror 不支援表 {table}(白名單:{sorted(_MIRRORED_TABLES)})")


async def mirror_rows(table: str, pk_vals: Sequence) -> None:
    """把權威庫中指定 id 的列 upsert 到品牌庫投影;權威庫已刪的 id 同步刪投影。

    以 SELECT * 實際值鏡射(非重放 SQL),兩庫 DEFAULT 生成值不會分岔。
    """
    _check_table(table)
    if not db.tech_db_enabled() or not pk_vals:
        return
    ids = list(pk_vals)
    try:
        tech = await db.require_tech_conn()
        cur = await tech.execute(
            f"SELECT {_select_cols(table)} FROM {table} WHERE id = ANY(%s)", (ids,))
        rows = await cur.fetchall()
        cols = [d.name for d in cur.description]
        cols, rows = _drop_private_cols(table, cols, rows)
        async with db.get_conn() as brand:
            if rows:
                collist = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))
                setlist = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "id")
                sql = (
                    f"INSERT INTO {table} ({collist}) VALUES ({placeholders}) "
                    f"ON CONFLICT (id) DO UPDATE SET {setlist}"
                )
                for row in rows:
                    await brand.execute(sql, _adapt_row(row))
            # SELECT 回來的 id 是 UUID 物件、呼叫端傳字串 —— 統一 str 比對,
            # 否則永遠視為 missing → 把剛 upsert 的投影列又刪掉(實測踩雷)。
            found = {str(row[cols.index("id")]) for row in rows} if rows else set()
            missing = [v for v in ids if str(v) not in found]
            if missing:
                await brand.execute(f"DELETE FROM {table} WHERE id = ANY(%s)", (missing,))
        logger.info("[TechMirror] %s 鏡射 %d 列(刪 %d)", table, len(rows), len(ids) - len(rows))
    except Exception:
        logger.error(
            "[TechMirror] %s 鏡射失敗(ids=%s)—— 權威庫已寫入、投影未同步,"
            "跑 scripts/db/split-tech-db.sh --verify 檢查漂移",
            table,
            ids,
            exc_info=True,
        )
        raise


async def ensure_technician_projection(technician_id: str) -> None:
    """指派/搶單前確保該師傅的 users+technicians 投影存在且最新(CR-0114 R4)。

    共用師傅庫模式下,品牌端讀候選走 authority(可見全部啟用中師傅),但
    work_orders.technician_id FK 指向品牌庫本地投影 —— 指派「從未投影過的
    師傅」會 FK 爆。故派工寫入前先 pull 該師傅身分列進品牌庫投影。
    單庫 fallback（tech_db 未啟用）→ no-op（讀寫同一顆庫,無投影概念）。
    """
    if not db.tech_db_enabled():
        return
    tech = await db.require_tech_conn()
    cur = await tech.execute(
        "SELECT user_id FROM technicians WHERE id = %s::uuid", (technician_id,))
    row = await cur.fetchone()
    user_id = row[0] if row else None
    # 先 users 後 technicians（FK 順序;user_id 可能為 NULL — admin 建的舊資料）
    if user_id is not None:
        await mirror_rows("users", [str(user_id)])
    await mirror_rows("technicians", [technician_id])


async def mirror_children(table: str, fk_col: str, parent_val) -> None:
    """子表全量刷新鏡射:以權威庫「該父鍵下的全部子列」重建品牌庫投影。

    適用整批替換的子集(如技師技能清單);先刪投影中該父鍵所有列,再逐列插入。
    """
    _check_table(table)
    if fk_col not in ("technician_id", "user_id"):
        raise ValueError(f"tech_mirror.mirror_children 不支援 fk_col={fk_col}")
    if not db.tech_db_enabled():
        return
    try:
        tech = await db.require_tech_conn()
        cur = await tech.execute(f"SELECT * FROM {table} WHERE {fk_col} = %s", (parent_val,))
        rows = await cur.fetchall()
        cols = [d.name for d in cur.description]
        cols, rows = _drop_private_cols(table, cols, rows)
        async with db.get_conn() as brand:
            await brand.execute(f"DELETE FROM {table} WHERE {fk_col} = %s", (parent_val,))
            if rows:
                collist = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))
                sql = f"INSERT INTO {table} ({collist}) VALUES ({placeholders})"
                for row in rows:
                    await brand.execute(sql, _adapt_row(row))
        logger.info("[TechMirror] %s(%s=%s)全量刷新 %d 列", table, fk_col, parent_val, len(rows))
    except Exception:
        logger.error(
            "[TechMirror] %s 子表鏡射失敗(%s=%s)", table, fk_col, parent_val, exc_info=True
        )
        raise
