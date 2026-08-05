"""WorkOrders 業務邏輯。

讀 work_orders 表 JOIN problem_cards 取 brand/model，mapping 成 OpenAPI schema：
  - work_orders.status (created/assigned/accepted/in_progress/completed/confirmed/cancelled)
    → WorkOrderStatus (16 enum) best-fit
  - work_orders.priority (low/normal/high/urgent) → Urgency (low/medium/high)
  - customer_address → district 解析（前綴市+區/鄉/鎮/縣）+ address 直通
  - estimated_price (FLOAT) → estimated_reward (decimal string with .2f)
  - started_at → actual_arrival（best-effort proxy；DB 沒獨立 arrival 欄位）
  - brand/model 從 problem_cards JOIN 取（DB work_orders 無此欄）

租戶隔離：透過 problem_cards JOIN conversations JOIN users.tenant_id（多 JOIN 一層）。
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from core.pagination import decode_cursor, encode_cursor
from services.problem_card_service import _DB_URGENCY_TO_API

logger = logging.getLogger("api.work_order_service")


_DB_STATUS_TO_API = {
    "created": "inquiring",
    "assigned": "assigned",
    "accepted": "accepted",
    "in_progress": "in_progress",
    "completed": "completed",
    "confirmed": "closed",  # OpenAPI 用 closed 表示客戶已確認結案
    "cancelled": "cancelled",
}

# 「市/縣 + 區/鄉/鎮」前綴；e.g. 「新北市板橋區」/「桃園市中壢區」
_DISTRICT_RE = re.compile(r"^([\u4e00-\u9fff]+?[市縣][\u4e00-\u9fff]+?[區鄉鎮市])")


def _parse_district(addr: str | None) -> str:
    if not addr:
        return ""
    m = _DISTRICT_RE.match(addr.strip())
    return m.group(1) if m else ""


def _coerce_decimal(price) -> str | None:
    if price is None:
        return None
    return f"{float(price):.2f}"


def _coerce_status(db_status: str | None) -> str:
    if not db_status:
        return "inquiring"
    return _DB_STATUS_TO_API.get(db_status, "inquiring")


def _coerce_urgency(db_priority: str | None) -> str:
    if not db_priority:
        return "medium"
    return _DB_URGENCY_TO_API.get(db_priority, "medium")


def _wo_row_to_dict(row: tuple) -> dict:
    """row 順序對齊 _WO_SELECT。"""
    address = row[5] or ""
    out: dict = {
        "id": str(row[0]),
        # 2026-08-02：原為無條件 str(row[1]) —— problem_card_id 為 NULL 時會變成字串
        # 'None'，回應模型是 UUID 型別 → ValidationError → **整支列表端點 500**。
        # 這與 problem_card_service._pc_row_to_dict 的 conversation_id 是同一個坑
        # （該處註解「UAT P1-1:手建卡無對話 → None(str(None) 會變 'None' 字串炸
        # response model)」已修，工單這支漏了）。
        # 實測 scratch 庫 629 張工單有 50 張 problem_card_id 為 NULL；prod 若出現
        # 手建工單（不由問題卡衍生）就會踩到，且症狀是整頁列表壞掉而非單筆異常。
        "problem_card_id": str(row[1]) if row[1] is not None else None,
        "status": _coerce_status(row[3]),
        "district": _parse_district(address),
        "address": address,
        "brand": row[6] or "",
        "model": row[7] or "",
        "urgency": _coerce_urgency(row[4]),
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
        # CR-0020 公單號（{2碼地區}-{6碼流水}）;nullable
        "document_number": row[14] if len(row) > 14 else None,
    }
    if row[2] is not None:
        out["technician_id"] = str(row[2])
    reward = _coerce_decimal(row[8])
    if reward is not None:
        out["estimated_reward"] = reward
    if row[9] is not None:
        out["scheduled_time"] = row[9].isoformat()
    if row[10] is not None:
        out["actual_arrival"] = row[10].isoformat()
    if row[11] is not None:
        out["completion_time"] = row[11].isoformat()
    # CR-0026 公單標準化欄位（index 15+，None 不輸出保 response 精簡）
    _STR_FIELDS = {
        15: "service_category", 16: "problem_type", 17: "serial_number",
        18: "door_type", 19: "door_thickness", 21: "warranty_status",
        23: "invoice_no", 24: "completion_status", 25: "status_reason",
    }
    for idx, key in _STR_FIELDS.items():
        if len(row) > idx and row[idx] is not None:
            out[key] = row[idx]
    if len(row) > 20 and row[20] is not None:
        out["is_interior_door"] = bool(row[20])
    if len(row) > 22 and row[22] is not None:
        out["purchase_date"] = row[22].isoformat()
    if len(row) > 26 and row[26] is not None:
        out["parent_work_order_id"] = str(row[26])
    if len(row) > 27:
        cfa = _coerce_decimal(row[27])
        if cfa is not None:
            out["customer_final_amount"] = cfa
    # CR-0043 Phase 2：客名/電話接回 + 設備/計費新欄（None 不輸出保 response 精簡）
    if len(row) > 28 and row[28] is not None:
        out["customer_name"] = row[28]
    if len(row) > 29 and row[29] is not None:
        out["customer_phone"] = row[29]
    if len(row) > 30 and row[30] is not None:
        out["dealer"] = row[30]
    if len(row) > 31 and row[31] is not None:
        out["install_date"] = row[31].isoformat()
    if len(row) > 32 and row[32] is not None:
        out["rain_exposure"] = row[32]
    if len(row) > 33 and row[33] is not None:
        out["special_door_surcharge"] = bool(row[33])
    if len(row) > 34 and row[34] is not None:
        out["payment_method"] = row[34]
    if len(row) > 35 and row[35] is not None:
        out["warranty_expiry_date"] = row[35].isoformat()
    if len(row) > 36 and row[36] is not None:
        out["teaching_note"] = row[36]
    # CR-0100：完工乾淨摘要（37）+ 功能測試逐項結果（38；jsonb，psycopg 已 decode 成 list）
    if len(row) > 37 and row[37] is not None:
        out["completion_summary"] = row[37]
    if len(row) > 38 and row[38]:
        out["function_tests"] = row[38]
    # CR-0178 UAT-0720-08：技師接單時間（39）
    if len(row) > 39 and row[39] is not None:
        out["accepted_at"] = row[39].isoformat()
    return out


def _mask_pool_privacy(wo: dict) -> dict:
    """接單前隱私遮蔽（UAT P1-4）：技師尚未接單前不揭露客戶個資。

    對齊 technician_line_service 最小揭露原則（區域＋品牌型號＋單號縮寫，
    不含客戶姓名/地址/電話）；接單後（my-orders，technician_id=本人）才回完整資訊。
    address 以 district（市＋區前綴）取代——WorkOrder schema 的 address 為
    required string，不可缺欄。
    """
    out = dict(wo)  # 不可變：建新 dict，不改原物件
    out.pop("customer_name", None)
    out.pop("customer_phone", None)
    out["address"] = out.get("district") or ""
    return out


_WO_SELECT = (
    "wo.id, wo.problem_card_id, wo.technician_id, wo.status, wo.priority, "
    "wo.customer_address, "
    # brand/model：優先 work_orders 自有副本（CR-0026），fallback problem_cards
    "COALESCE(wo.brand, pc.brand), COALESCE(wo.model, pc.model), "
    "wo.estimated_price, wo.scheduled_at, wo.started_at, wo.completed_at, "
    "wo.created_at, wo.updated_at, wo.document_number, "
    # CR-0026 公單標準化欄位（index 15+，append-only 保既有索引不變）
    "wo.service_category, wo.problem_type, wo.serial_number, wo.door_type, "
    "wo.door_thickness, wo.is_interior_door, wo.warranty_status, wo.purchase_date, "
    "wo.invoice_no, wo.completion_status, wo.status_reason, wo.parent_work_order_id, "
    "wo.customer_final_amount, "
    # CR-0043 Phase 2（index 28+，append-only）：客名/電話接回 + migration 052 五欄
    "wo.customer_name, wo.customer_phone, wo.dealer, wo.install_date, "
    "wo.rain_exposure, wo.special_door_surcharge, wo.payment_method, "
    # CR-0047（index 35）：保固到期日；CR-0050（index 36）：教學紀錄
    "wo.warranty_expiry_date, wo.teaching_note, "
    # CR-0100（index 37/38）：完工乾淨摘要 + 功能測試逐項結果
    "wo.completion_summary, wo.function_tests, "
    # CR-0178 UAT-0720-08（index 39）：技師接單時間（accept/claim 寫入，上 envelope 供時間軸）
    "wo.accepted_at"
)

# UAT P1-1:手建問題卡(電話進線)無 conversation → 整鏈改 LEFT JOIN,
# tenant guard 一律 COALESCE(wo.tenant_id, u.tenant_id)(舊單 wo.tenant_id 可能
# NULL 走 user 鏈;手建卡單 wo.tenant_id 必有值)。原 INNER 鏈會讓手建卡的
# 工單在列表/詳情/派工全鏈 404。
_WO_JOIN = (
    "FROM work_orders wo "
    "LEFT JOIN problem_cards pc ON wo.problem_card_id = pc.id "
    "LEFT JOIN conversations c ON pc.conversation_id = c.id "
    "LEFT JOIN users u ON c.user_id = u.id"
)


async def list_orders(
    *,
    tenant_id: str,
    cursor: str | None,
    limit: int,
    problem_card_id: str | None = None,
    technician_id: str | None = None,
    status: str | list[str] | None = None,
    brand: str | None = None,
    created_after: str | None = None,
    keyword: str | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    where = ["COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid"]
    args: list = [tenant_id]

    if problem_card_id:
        where.append("wo.problem_card_id = %s::uuid")
        args.append(problem_card_id)

    if technician_id:
        where.append("wo.technician_id = %s::uuid")
        args.append(technician_id)

    # UAT R3-7：status 可多值（list）取聯集——前端把群組值映射為多個原始
    # status 重複帶 query param；單值字串維持向後相容。
    if status:
        statuses = [status] if isinstance(status, str) else [s for s in status if s]
        if statuses:
            placeholders = ", ".join(["%s"] * len(statuses))
            where.append(f"wo.status IN ({placeholders})")
            args.extend(statuses)

    if brand:
        where.append("pc.brand = %s")
        args.append(brand)

    if created_after:
        where.append("wo.created_at >= %s::timestamptz")
        args.append(created_after)

    if keyword:
        # 公單號（document_number，如 TP-000001）一併納入搜尋 —— 讓使用者用可讀編號
        # 找工單（如報價頁選工單），免貼內部 UUID。additive：response schema 不變。
        where.append(
            "(wo.customer_name ILIKE %s OR wo.customer_address ILIKE %s "
            "OR wo.customer_phone ILIKE %s OR wo.document_number ILIKE %s)"
        )
        like = f"%{keyword}%"
        args.extend([like, like, like, like])

    cur_data = decode_cursor(cursor)
    if cur_data and "ts" in cur_data and "id" in cur_data:
        where.append("(wo.created_at, wo.id) < (%s, %s::uuid)")
        args.extend([cur_data["ts"], cur_data["id"]])

    sql = (
        f"SELECT {_WO_SELECT} {_WO_JOIN} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY wo.created_at DESC, wo.id DESC "
        f"LIMIT %s"
    )
    args.append(limit + 1)
    cur = await db_module._conn.execute(sql, args)
    rows = await cur.fetchall()

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_wo_row_to_dict(r) for r in rows]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor({"ts": last[12].isoformat(), "id": str(last[0])})

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def _fetch_technician_for_user(user_id: str | None) -> dict | None:
    """依 users.id 反查 technicians（搶單 claim / 派工資格檢查用）。無對應列回 None。"""
    if not user_id:
        return None
    cur = await db_module._conn.execute(
        "SELECT id, status FROM technicians WHERE user_id = %s::uuid",
        (user_id,),
    )
    row = await cur.fetchone()
    return {"id": str(row[0]), "status": row[1]} if row else None


#: 技師身分查無對應 technicians 列時使用的過濾值 —— nil UUID 保證比不中任何工單。
#: 用 sentinel 而非「不加過濾」，是因為後者等於 fail-open（正是本次要修的缺陷）。
_NO_TECHNICIAN_SENTINEL = "00000000-0000-0000-0000-000000000000"


async def technician_scope_filter(
    *, actor_role: str | None, actor_user_id: str | None, requested: str | None
) -> str | None:
    """工單列表的角色 scope 收斂（2026-07-31，TC-DISPATCH-05 / TC-PLT-SURFACE-01）。

    背景：`GET /api/v1/work-orders`（v1）與 `GET /tenants/{tid}/work-orders`（v2）
    都只有 `Depends(require_tenant)`，`technician_id` 純粹是「可選過濾參數」。
    實測技師 token 拿到的回應與品牌 admin **位元組完全相同**（含未指派給他的工單、
    customer_name、customer_phone）。TC-DISPATCH-05 要求技師只看得到自己的派工。

    為什麼不是回 403：師傅站的「我的工單」正常功能就是讀這兩支，擋掉會直接壞掉。
    正解是**收斂 scope** 而不是拒絕存取。

    為什麼要**忽略** client 傳來的 technician_id：否則技師只要把參數換成別人的
    technicians.id 就能繞過（實測 v1 可行）。呼叫端傳什麼一律不採信。

    非技師角色（admin / dispatcher / ops…）維持原行為：沿用傳入的過濾參數。
    """
    if actor_role != "technician":
        return requested
    tech = await _fetch_technician_for_user(actor_user_id)
    if not tech:
        # 有技師 token 但品牌庫查無對應 technicians 列 → 不得退回「不過濾」
        logger.warning(
            "technician token 查無對應 technicians 列 user=%s → 工單列表收斂為空",
            str(actor_user_id)[:8],
        )
        return _NO_TECHNICIAN_SENTINEL
    return tech["id"]


async def assert_technician_may_read(
    *, wo_id: str, actor_role: str | None, actor_user_id: str | None
) -> None:
    """技師讀「單筆工單／其子資源」的擁有權守衛（2026-08-02）。

    **為什麼要有這支**：2026-08-02 補上工單**列表**的角色收斂後，SC-13～19 探針實跑
    抓到收斂只做了一半 —— 單筆與子資源（quote-items / document / evidence-package /
    events）全都只有 `Depends(require_tenant)`，技師拿別人的工單 id 直接打就 200：
      - detail 與 admin 逐欄比對只差 customer_phone 與 address
      - quote-items 品項、對外價、總額全露（unit_price 有遮蔽，但那只是成本欄）
      - **document 回 200 application/pdf，位元組數與 admin 取得的完全一致**
    對照組已排除「守衛整支沒掛」：換租戶 id 時 admin 與技師都 403 CROSS_TENANT_READ，
    所以缺的是同租戶內的 per-work-order 擁有權檢查。

    **可見範圍不能只寫「指派給我」** —— 搶單池的單本來就要讓技師看得到才能決定接不接。
    對齊 `list_work_order_pool` 對技師的過濾（status='created' AND technician_id IS NULL）：
        指派給我  OR  未被認領且仍在 created  → 放行
        其餘                                  → 擋

    **回 404 而非 403**：技師沒有任何合法管道得知這張單存在（自己的列表濾掉了、
    池子也濾掉了），回 403 等於確認存在性、可被拿來枚舉租戶內的工單 id。
    真正的原因記在 server log，營運查得到、客戶端問不出來。

    非技師角色（admin / ops / dispatcher / cs…）不受本守衛影響。
    """
    if actor_role != "technician":
        return
    tech = await _fetch_technician_for_user(actor_user_id)
    cur = await db_module._conn.execute(
        "SELECT technician_id, status FROM work_orders WHERE id = %s::uuid", (wo_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    assigned_to, status = (str(row[0]) if row[0] else None), row[1]
    if tech and assigned_to == tech["id"]:
        return
    if assigned_to is None and status == "created":
        return  # 搶單池可見
    logger.warning(
        "技師讀取未授權工單被擋 wo=%s actor_user=%s assigned_to=%s status=%s",
        wo_id[:8], str(actor_user_id)[:8], (assigned_to or "-")[:8], status,
    )
    raise ApiError("NOT_FOUND", "Work order not found", 404)


async def list_work_order_pool(
    *,
    tenant_id: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> dict:
    """技師案件池：可搶接的無主工單。

    UAT P1-4 裁決：已指派（technician_id 非空／status 非 created）的單不得
    出現在技師案件池——派給自己的單走 my-orders「進行中」分頁追蹤，池只留
    created 且未指派的可搶單，杜絕「已指派仍掛在池」的混淆。
    admin/後台視角維持全列（created + assigned；派工佇列監控用）。
    技師視角另套接單前隱私遮蔽（_mask_pool_privacy：不回客戶姓名/電話/完整地址）。
    優先序：urgency=high > medium > low；同等級依 created_at ASC 列出
    （越早建立越優先）。預設不分頁，上限 100 筆。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if actor_role == "technician":
        status_filter = "  AND wo.status = 'created' AND wo.technician_id IS NULL "
    else:
        status_filter = "  AND wo.status IN ('created', 'assigned') "

    sql = (
        f"SELECT {_WO_SELECT} {_WO_JOIN} "
        f"WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid "
        f"{status_filter}"
        f"ORDER BY "
        f"  CASE wo.priority "
        f"    WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
        f"    WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 "
        f"  END ASC, "
        f"  wo.created_at ASC, wo.id ASC "
        f"LIMIT 100"
    )
    cur = await db_module._conn.execute(sql, (tenant_id,))
    rows = await cur.fetchall()
    items = [_wo_row_to_dict(r) for r in rows]
    if actor_role == "technician":
        items = [_mask_pool_privacy(i) for i in items]
    return {"items": items, "next_cursor": None, "has_more": False}


# CR-0100 SLA 政策：三級時數（high/medium/low），SLA 計時起點＝created_at（M18 config
# sla_policy 治理，不寫死；emergency 4h 留未來）。sla_deadline 不落欄，讀時 computed。
_SLA_POLICY_DEFAULTS = {
    "hours_by_urgency": {"high": 8, "medium": 24, "low": 48},
    "clock_start": "created_at",
}


async def _compute_sla_deadline(created_at_iso: str | None, urgency: str | None) -> str | None:
    """SLA deadline = created_at + hours_by_urgency[urgency]（缺政策/時間 → None）。"""
    if not created_at_iso or not urgency:
        return None
    from datetime import datetime, timedelta

    from services import config_m18_service

    policy = dict(_SLA_POLICY_DEFAULTS)
    cfg = await config_m18_service.read_global_value(namespace="sla_policy")
    if cfg:
        policy.update(cfg)
    hours = (policy.get("hours_by_urgency") or {}).get(urgency)
    if hours is None:
        return None
    try:
        base = datetime.fromisoformat(created_at_iso)
        return (base + timedelta(hours=float(hours))).isoformat()
    except (ValueError, TypeError):
        return None


async def get_order(
    *,
    tenant_id: str,
    wo_id: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> dict:
    """工單詳情。actor 為技師且該單非本人名下（池詳情／搶單前預覽）時，
    套接單前隱私遮蔽（UAT P1-4：接單後才揭露客戶姓名/電話/完整地址）。
    未帶 actor（後台/內部呼叫）行為不變。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT {_WO_SELECT} {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    out = _wo_row_to_dict(row)
    if actor_role == "technician":
        tech = await _fetch_technician_for_user(actor_user_id)
        if not tech or out.get("technician_id") != tech["id"]:
            out = _mask_pool_privacy(out)
    # CR-0100：SLA deadline computed（單筆詳情用；列表視圖不需倒數，省一次 config 讀取）
    sla = await _compute_sla_deadline(out.get("created_at"), out.get("urgency"))
    if sla:
        out["sla_deadline"] = sla
    return out


def _map_service_category(pc_category: str | None) -> str:
    """CR-0043 HD-1：pc.category（自由字串，可中/英）→ work_orders.service_category
    enum（install/warranty_in/warranty_out/repair）。無法判定預設 repair，可後台 PATCH 改。"""
    c = (pc_category or "").strip().lower()
    if not c:
        return "repair"
    if any(k in c for k in ("install", "安裝", "新裝", "新機", "裝機")):
        return "install"
    if any(k in c for k in ("warranty_in", "保內", "保内")):
        return "warranty_in"
    if any(k in c for k in ("warranty_out", "保外")):
        return "warranty_out"
    return "repair"


async def create_from_problem_card(
    *,
    tenant_id: str,
    pc_id: str,
    customer_address: str | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    created_by: str | None = None,
) -> tuple[dict, bool]:
    """從 confirmed ProblemCard 建立 WorkOrder（F-002 客服審 PC → 開 WO）。

    前置條件：PC.status = 'confirmed' 且未已存在對應 WO。
    Idempotency：同 PC 重複呼叫回既存 WO（created_flag=False，HTTP 200）；
    新建回 created_flag=True（HTTP 201）。

    customer_address / name / phone：優先用 caller 帶入；address 其次取
    pc.location（UAT P2-8：本案蒐集的服務地址），再 fallback 到 user 的
    profile（users.address/display_name/phone）。address 三者皆無 → 422。

    urgency / priority：PC.urgency 與 WO.priority 共用 DB enum
    (low/normal/high/urgent)，直接 pass-through。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 1. 取 PC + 同 transaction lock 防止 race（兩個並發 convert 同一張 PC）
    cur = await db_module._conn.execute(
        "SELECT pc.status, pc.urgency, "
        "       u.address, u.display_name, u.phone, "
        # CR-0026：建單時把設備辨識 + 問題類型 + 媒體從 PC 複製進 work_order
        # UAT P2-8：pc.location（本案蒐集的服務地址）一併帶出供地址 fallback
        # UAT P1-1：手建卡（無對話）→ LEFT JOIN；tenant guard 改用 pc.tenant_id
        # （CR-0132 直接租戶欄）；contact_phone/extracted_fields 供客戶資訊 fallback
        "       pc.brand, pc.model, pc.category, pc.media_urls, pc.emergency_class, "
        "       pc.location, pc.contact_phone, pc.extracted_fields, "
        # CR-0178 UAT-0720-09 續 2：序號一併帶入（原 CR-0026 只複製 brand/model/媒體，獨漏 serial）
        "       pc.serial "
        "FROM problem_cards pc "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid "
        "FOR UPDATE OF pc",
        (pc_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Problem card not found", 404)

    (pc_status, pc_urgency, user_address, user_name, user_phone,
     pc_brand, pc_model, pc_category, pc_media, pc_emergency_class,
     pc_location, pc_contact_phone, pc_extracted, pc_serial) = row

    # UAT P1-1：手建卡客戶資訊 fallback——caller > 卡上(extracted/contact_phone) > user profile
    pc_customer_name = None
    if pc_extracted:
        _ext = pc_extracted if isinstance(pc_extracted, dict) else {}
        pc_customer_name = (_ext.get("customer_name") or "").strip() or None
    user_name = user_name or pc_customer_name
    user_phone = user_phone or pc_contact_phone

    if pc_status != "confirmed":
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot convert problem card in status '{pc_status}'; expected 'confirmed'",
            409,
        )

    # 2. Idempotency: existing WO with same problem_card_id?
    cur = await db_module._conn.execute(
        "SELECT id FROM work_orders "
        "WHERE problem_card_id = %s::uuid "
        "ORDER BY created_at ASC LIMIT 1",
        (pc_id,),
    )
    existing = await cur.fetchone()
    if existing:
        wo = await get_order(tenant_id=tenant_id, wo_id=str(existing[0]))
        return wo, False

    # 2.5 報價先行 gate（CR-0128 / ADR-015① / BR-WO-01「線上報價 → 客人確認 → 才開單派工」）：
    #     標準路徑須有客戶已確認（accepted）報價（無/進行中 → 425；全數失效 → 409）；
    #     急件 carve-out（pc.emergency_class 四類）跳過報價直接開單、事後補審（4h timer＝1.2.2）。
    from services import quote_engine_service as _qe

    if pc_emergency_class is None:
        await _qe.assert_pc_quote_confirmed(tenant_id=tenant_id, problem_card_id=pc_id)

    # 3. Resolve customer info（caller override > PC location > user profile fallback）
    #    UAT P2-8：pc.location 為本案蒐集的服務地址（L3 補址欄），比 user profile
    #    的通用地址更準——caller 未帶時優先取卡上地址，避免有卡址仍 422。
    #    CR-0165 F6a：專用碼取代泛用 VALIDATION_ERROR（比照結案 ADDRESS_REQUIRED_FOR_CLOSE）
    final_address = customer_address or pc_location or user_address
    if not final_address:
        raise ApiError(
            "ADDRESS_REQUIRED_FOR_CONVERT",
            "開單前須有服務地址——客戶資料無地址時請於轉工單時填寫",
            422,
        )
    final_name = customer_name or user_name
    final_phone = customer_phone or user_phone
    # PC.urgency 與 WO.priority 共用 DB enum (low/normal/high/urgent)，直接 pass-through
    priority = pc_urgency or "normal"

    # 4. INSERT（CR-0020：建立時依地址發公單號 {2碼地區}-{6碼流水}，per-region 原子遞增）
    #    CR-0026：複製設備辨識(brand/model)/問題類型(problem_type)/媒體(photos)，並寫 tenant_id
    #    UAT R3-6：autocommit 下步驟 1 的 FOR UPDATE 鎖不跨語句，步驟 2 的
    #    get-or-create 在併發下可雙雙 miss → 靠 migration 110 的 partial UNIQUE
    #    （problem_card_id 限原始單）DB 兜底；撞 UNIQUE = 別的請求已建 → 回既有單
    #    （get 語意，created_flag=False）。
    from psycopg import errors as _pg_errors

    try:
        insert_cur = await db_module._conn.execute(
            "INSERT INTO work_orders "
            "  (problem_card_id, status, priority, "
            "   customer_name, customer_phone, customer_address, created_by, document_number, "
            "   brand, model, problem_type, service_category, photos, tenant_id, quote_gate_applied, "
            "   serial_number) "
            "VALUES (%s::uuid, 'created', %s, %s, %s, %s, "
            "        %s::uuid, generate_wo_number(%s), "
            "        %s, %s, %s, %s, %s::jsonb, %s::uuid, TRUE, %s) "
            "RETURNING id",
            # CR-0043：problem_type 留 pc.category（問題本質）；service_category 另映射 enum（修死欄 bug）
            # CR-0128：quote_gate_applied=TRUE——gate 後新單，結案硬閘驗報價確認（存量單 FALSE 豁免）
            (pc_id, priority, final_name, final_phone, final_address, created_by, final_address,
             pc_brand, pc_model, pc_category, _map_service_category(pc_category),
             json.dumps(pc_media, ensure_ascii=False) if pc_media else None, tenant_id,
             pc_serial or None),
        )
    except _pg_errors.UniqueViolation as exc:
        constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
        if constraint in (None, "uq_work_orders_problem_card"):
            cur = await db_module._conn.execute(
                "SELECT id FROM work_orders "
                "WHERE problem_card_id = %s::uuid "
                "ORDER BY created_at ASC LIMIT 1",
                (pc_id,),
            )
            existing = await cur.fetchone()
            if existing:
                logger.info(
                    "convert 併發撞 UNIQUE(problem_card_id) → 回既有單 pc=%s wo=%s",
                    pc_id, existing[0],
                )
                wo = await get_order(tenant_id=tenant_id, wo_id=str(existing[0]))
                return wo, False
        raise
    new_row = await insert_cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to insert work order", 500)
    new_wo_id = str(new_row[0])

    # CR-0193 / TC-WO-01：建單事件。正典 20_Test_Cases.md:258 直接驗這一筆。
    # 刻意放在 UNIQUE 回放路徑（上方 return wo, False）之後——併發撞號時事件已由
    # 贏家寫過，回放路徑再寫一筆會讓同一次轉換出現兩筆 'created'。
    await _insert_wo_event(
        wo_id=new_wo_id, tenant_id=tenant_id, actor_user_id=created_by,
        event_type="created",
        payload={
            "origin": "problem_card",
            "problem_card_id": pc_id,
            "urgency": pc_urgency,
            # 急件 carve-out：跳過「報價須客戶確認」硬閘、改事後補審（CR-0128/CR-0129）
            "emergency_class": pc_emergency_class,
            "quote_gate_applied": True,
        },
    )

    # CR-0128：PC 階段報價回填綁定工單（可讀編號 TP-xxxxxx-Qn 隨之成立）；
    # 急件 carve-out 則建 retrospective_audit_only 佔位報價供事後補審（1.2.2 timer 追蹤）。
    if pc_emergency_class is None:
        await _qe.bind_quotes_to_work_order(
            tenant_id=tenant_id, problem_card_id=pc_id, work_order_id=new_wo_id)
        # CR-0163：補開延後的應收發票——卡階段 accept 時 transition 記
        # 「invoice deferred until convert」並承諾由本流程補開，但承諾從未被
        # 實作 → 報價先行主路徑每張工單都靜默漏開發票（金流斷層）。
        # best-effort 比照 accept 即開票路徑：失敗 ERROR log（人工 from-quote
        # 補開），不阻斷開單；invoices.work_order_id UNIQUE 天然冪等。
        try:
            arow = await (await db_module._conn.execute(
                "SELECT id FROM quote "
                "WHERE work_order_id = %s::uuid AND tenant_id = %s::uuid "
                "  AND state = 'accepted' "
                "ORDER BY updated_at DESC LIMIT 1", (new_wo_id, tenant_id))).fetchone()
            if arow:
                from services import invoice_service
                inv = await invoice_service.create_from_quote(
                    tenant_id=tenant_id, quote_id=str(arow[0]))
                logger.info("convert 補開延後發票 wo=%s invoice=%s", new_wo_id, inv.get("id"))
        except Exception as exc:  # noqa: BLE001 — 開票失敗不阻斷開單（帳務下游解耦）
            logger.error(
                "wo %s created but deferred invoice creation FAILED (manual from-quote needed): %s",
                new_wo_id, exc)
    else:
        await _qe.create_quote(
            tenant_id=tenant_id, work_order_id=new_wo_id, created_by=created_by,
            urgent=True, initial_state="retrospective_audit_only")
        # 15_SDS §4.5 步驟1：急件跳過事前報價開單，audit 記 emergency_bypass（fail-soft）
        from services.audit_log_service import log_event
        await log_event(
            event_type="work_order",
            actor_id=created_by,
            actor_role="customer_service",
            action="emergency_bypass",
            target_type="work_order",
            target_id=new_wo_id,
            payload={
                "emergency_class": pc_emergency_class,
                "problem_card_id": pc_id,
                "policy": "BR-WO-01 carve-out（ADR-015①/CR-0128）",
                "retrospective_audit": "required within window after completion（CR-0129）",
            },
        )

    # CR-0096：標記 PC 已轉工單 → 該卡不再 active，同 conversation（同一 LINE 客人）
    # 之後的新問題可開「新卡」而非 append 進這張已派工的舊卡。
    await db_module._conn.execute(
        "UPDATE problem_cards SET converted_at = NOW() WHERE id = %s::uuid",
        (pc_id,),
    )

    # 5. WS publish + return
    wo = await _publish_and_return(
        tenant_id=tenant_id, wo_id=new_wo_id, event_type="work_order.created"
    )
    # CR-0169:建單進搶單池 → LINE 廣播(開關過濾在 tech 端;fail-soft)
    await _notify_tech_line("/api/v1/internal/technicians/notify-pool", {
        "tenant_id": tenant_id,
        "work_order": _tech_line_wo_summary(wo),
    })
    return wo, True


# CR-0043 Tier①：PATCH 可設欄位白名單（補「寫入路徑稀薄」缺口；enum 由 app 驗證）
_PATCHABLE_FIELDS: dict[str, set | None] = {
    "service_category": {"install", "warranty_in", "warranty_out", "repair"},
    "serial_number": None,
    "brand": None,
    "model": None,
    # UAT-0718 N2：派工閘要求 problem_type（_DISPATCH_REQUIRED）——補進 PATCH 白名單，
    # 缺欄單（含手建卡急件）才有 UI 路可過閘。值域對齊 problem_cards.category 自由字串
    # （工單建立時即複製 pc.category，DB VARCHAR(100) 無 enum constraint）。
    "problem_type": None,
    "door_type": None,
    "door_thickness": None,
    "is_interior_door": None,           # bool
    "warranty_status": {"in_warranty", "out_warranty", "not_applicable"},
    "purchase_date": None,              # ISO date
    "install_date": None,              # ISO date
    "invoice_no": None,
    "dealer": None,
    "rain_exposure": {"indoor", "outdoor_covered", "outdoor_exposed"},
    "special_door_surcharge": None,     # bool
    "payment_method": {"cash", "bank_transfer", "credit_card", "line_pay"},
    "customer_name": None,
    "customer_phone": None,
    "customer_address": None,
}


def _auto_warranty(brand, purchase_date, install_date):
    """CR-0047：序號/購買日/裝機日 → 保固到期日 + 保內/保外（接 warranty_service 引擎）。

    錨點優先 purchase_date，缺則 install_date；兩者皆無 → (None, None) 不自動算。
    期間由 warranty_service.resolve_period_months（brand override，預設 24 月）。回 (expiry_date, status)。
    """
    from datetime import date as _date
    from services.warranty_service import (
        DEFAULT_WARRANTY_CONFIG, compute_warranty_end, is_within_warranty, resolve_period_months,
    )

    def _to_date(v):
        if v is None:
            return None
        if isinstance(v, _date):
            return v
        try:
            return _date.fromisoformat(str(v)[:10])
        except ValueError:
            return None

    start = _to_date(purchase_date) or _to_date(install_date)
    if start is None:
        return None, None
    period = resolve_period_months(brand, DEFAULT_WARRANTY_CONFIG)
    end = compute_warranty_end(start, period)
    return end, ("in_warranty" if is_within_warranty(_date.today(), end) else "out_warranty")


async def update_wo_fields(*, tenant_id: str, wo_id: str, fields: dict) -> dict:
    """CR-0043 Tier①：後台設定工單欄位（service_category/serial/door/warranty/payment 等）。

    只允許 _PATCHABLE_FIELDS 白名單；enum 欄位驗值；未知/空 → 422。
    租戶隔離走 users join（與 get_order 一致）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 過濾白名單 + 驗 enum
    sets: list[str] = []
    args: list = []
    for key, val in fields.items():
        if key not in _PATCHABLE_FIELDS:
            continue
        allowed = _PATCHABLE_FIELDS[key]
        if val is not None and allowed is not None and str(val) not in allowed:
            raise ApiError(
                "VALIDATION_ERROR",
                f"Invalid value for {key}: {val!r}; allowed={sorted(allowed)}",
                422,
            )
        sets.append(f"{key} = %s")
        args.append(val)

    if not sets:
        raise ApiError("VALIDATION_ERROR", "No patchable field provided", 422)

    # 確認 WO 存在且屬本租戶（get_order 會 404；先驗再 UPDATE 避免跨租戶寫）+ 取既有值供自動保固
    existing = await get_order(tenant_id=tenant_id, wo_id=wo_id)

    # CR-0047：自動保固計算（patch 動到 serial/購買日/裝機日/brand 且未手動指定 warranty_status）
    if "warranty_status" not in fields and {"serial_number", "purchase_date", "install_date", "brand"} & fields.keys():
        eff_brand = fields.get("brand", existing.get("brand"))
        eff_purchase = fields.get("purchase_date", existing.get("purchase_date"))
        eff_install = fields.get("install_date", existing.get("install_date"))
        w_end, w_status = _auto_warranty(eff_brand, eff_purchase, eff_install)
        if w_status:
            sets.append("warranty_status = %s")
            args.append(w_status)
            sets.append("warranty_expiry_date = %s")
            args.append(w_end)

    args.extend([wo_id, tenant_id])
    # UAT-0718 N2：原本 FROM pc, c, u 內連結——手建卡（conversation_id NULL）工單
    # 永遠 join 不到 → UPDATE 靜默 0 列（P1-B LEFT JOIN 掃描的同型漏網）。
    # 改與 get_order 相同的 COALESCE(wo.tenant_id, 鏈上 u.tenant_id) 語意：
    # wo.tenant_id 有值直接比對；否則走 pc→c→u 反查（子查詢無列時為 NULL 不放行）。
    await db_module._conn.execute(
        f"UPDATE work_orders wo SET {', '.join(sets)}, updated_at = now() "
        "WHERE wo.id = %s::uuid "
        "  AND COALESCE(wo.tenant_id, ("
        "        SELECT u.tenant_id FROM problem_cards pc "
        "        JOIN conversations c ON pc.conversation_id = c.id "
        "        JOIN users u ON c.user_id = u.id "
        "        WHERE pc.id = wo.problem_card_id"
        "  )) = %s::uuid",
        args,
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.updated"
    )


async def reopen_order(
    *, tenant_id: str, wo_id: str, reason: str, created_by: str | None = None
) -> dict:
    """CR-0043 Tier②／BR-M05-02：返修/reopen — 建「子單」連回原工單，不覆蓋原單歷史。

    原單須存在（任意狀態）；reason 必填（BR-M05-01）。子單複製原單設備/客戶欄位，
    parent_work_order_id 連回原單、發新公單號、status='created' 重新進派工流程。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason required for reopen (BR-M05-01)", 422)

    # 確認原單存在且屬本租戶（get_order 會 404 / 跨租戶擋）
    await get_order(tenant_id=tenant_id, wo_id=wo_id)

    insert_cur = await db_module._conn.execute(
        "INSERT INTO work_orders "
        "  (problem_card_id, status, priority, customer_name, customer_phone, "
        "   customer_address, created_by, document_number, brand, model, serial_number, "
        "   door_type, door_thickness, is_interior_door, service_category, problem_type, "
        "   parent_work_order_id, status_reason, tenant_id) "
        "SELECT problem_card_id, 'created', priority, customer_name, customer_phone, "
        "   customer_address, %s::uuid, generate_wo_number(customer_address), brand, model, "
        "   serial_number, door_type, door_thickness, is_interior_door, service_category, "
        "   problem_type, id, %s, tenant_id "
        "FROM work_orders WHERE id = %s::uuid "
        "RETURNING id",
        (created_by, reason.strip(), wo_id),
    )
    new_row = await insert_cur.fetchone()
    if not new_row:
        raise ApiError("INTERNAL_ERROR", "Failed to reopen work order", 500)
    child_id = str(new_row[0])
    # CR-0193：reopen 產生**新工單**，兩邊 timeline 都要接得上——
    # 母單只寫「被重開為 X」（否則母單看起來像被棄置），子單寫 'created' 對齊
    # create_from_problem_card 的慣例並回指母單。
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=created_by,
        event_type="reopened",
        payload={"reason": reason.strip(), "child_work_order_id": child_id},
    )
    await _insert_wo_event(
        wo_id=child_id, tenant_id=tenant_id, actor_user_id=created_by,
        event_type="created",
        payload={"origin": "reopen", "reopened_from_work_order_id": wo_id,
                 "reason": reason.strip()},
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=child_id, event_type="work_order.reopened"
    )


# ── 工單狀態機（DB 7 值）中央轉移表（CR-0128 G6 / ADR-015 / BRD §5.7）──────────
# 業務對映（BRD §5.7 視角 → DB 值）：created=公單成立（報價已客戶確認或急件 carve-out）、
# assigned=已派工、accepted=技師接單、in_progress=施工中（含現場修正輪核可後回復）、
# completed=技師完工（硬閘：地址＋報價確認＋存證）、confirmed=客戶確認結案（API 讀值
# 映射 closed）、cancelled=取消。
# 本表為狀態機正典；下方各 `*_FROM` 守衛集合是它的逐動作投影（enforcement 落點），
# 新增/修改轉移時兩邊必須同步（測試 test_cr_0128 對帳）。
_WO_TRANSITIONS: dict[str, set[str]] = {
    "created":     {"assigned", "accepted", "cancelled"},                 # 派工／技師搶單 claim／取消
    "assigned":    {"assigned", "accepted", "created", "cancelled"},      # 重派換人／接單／技師拒單回池／取消
    "accepted":    {"assigned", "in_progress", "completed", "cancelled"}, # 改派／開工／完工／取消
    "in_progress": {"assigned", "completed", "cancelled"},                # 改派／完工／取消
    "completed":   {"confirmed"},                                         # 客戶確認結案
    "confirmed":   set(),                                                 # 終局
    "cancelled":   set(),                                                 # 終局
}

_ACCEPT_FROM = {"assigned"}
_REJECT_FROM = {"assigned"}  # CR-0166 R1：技師拒單（assigned → created 回池擴大候選）
_COMPLETE_FROM = {"accepted", "in_progress"}
_CANCEL_FROM = {"created", "assigned", "accepted", "in_progress"}
_ASSIGN_FROM = {"created", "assigned"}  # 允許重派（assigned → assigned 換人）
# Flow 8 二次派工：admin 強制改派可從 accepted / in_progress 收回（含 assigned，
# 與 assign_order 重疊但語意不同：reassign 明確記錄 old→new + dispatch_log action='reassign'）
_REASSIGN_FROM = {"assigned", "accepted", "in_progress"}
# 升級可從任何「未結案」狀態觸發；completed/confirmed/cancelled 視為終局不可升級
_ESCALATE_FROM = {"created", "assigned", "accepted", "in_progress"}
_ESCALATE_LEVELS = {"operations_manager", "tenant_admin"}
# 客戶確認結案：只能從技師完工後的 completed 狀態進入 confirmed
_CONFIRM_FROM = {"completed"}
# 改期可從技師接單後 / 執行中觸發；created 階段尚未排程不需改期
_RESCHEDULE_FROM = {"assigned", "accepted", "in_progress"}
# 24h 內改期次數上限（業務規則：避免技師連續推遲）
_RESCHEDULE_LIMIT_24H = 3

# CR-0026 / BR-M05-03：派工前必填欄位（三級必填的「派工前必填」級；預設值待業主確認）
_DISPATCH_REQUIRED = (
    ("brand", "品牌"),
    ("model", "型號"),
    ("customer_address", "地址"),
    ("problem_type", "問題類型"),
)


async def _assert_dispatch_ready(wo_id: str) -> None:
    """派工 gate（BR-M05-03）：派工前必填欄位缺 → 422。

    依 CR-0026 §8 預設三級必填分類：品牌/型號/地址/問題類型 為「派工前必填」。
    照片 photos 列為建議（非硬擋），避免無媒體案件卡死派工；可後續調整。
    """
    cols = ", ".join(f[0] for f in _DISPATCH_REQUIRED)
    cur = await db_module._conn.execute(
        f"SELECT {cols} FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    if not row:
        return  # not-found 交由後續 status 流程處理
    missing = [
        label for (_key, label), val in zip(_DISPATCH_REQUIRED, row)
        if val is None or (isinstance(val, str) and not val.strip())
    ]
    if missing:
        raise ApiError(
            "DISPATCH_PRECONDITION_FAILED",
            f"派工前必填欄位未齊（缺：{'、'.join(missing)}）",
            422,
        )


async def _publish_and_return(
    *, tenant_id: str, wo_id: str, event_type: str
) -> dict:
    """共用：fetch 最新 order → 推 work-orders/{id} 事件 + dispatch-queue 變化通知 → 回傳。"""
    order = await get_order(tenant_id=tenant_id, wo_id=wo_id)
    try:
        from realtime.ws_hub import hub  # 延遲 import 避免循環

        await hub.publish(
            f"/realtime/work-orders/{wo_id}",
            {
                "type": event_type,
                "payload": {"event": event_type, "work_order": order},
            },
        )
        await hub.publish(
            "/realtime/dispatch-queue",
            {
                "type": "work_order.state_change",
                "payload": {
                    "work_order_id": wo_id,
                    "event": event_type,
                    "status": order.get("status"),
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish work_order state failed (non-fatal)")
    # CR-0166 R4：dual-write 工單生命週期事件到 Kafka（KAFKA_BOOTSTRAP 未設=no-op；
    # 失敗 fail-soft，WS＋DB 為即時/保底路徑）。餵技師平台 CQRS 投影＋SigNoz（ADR-017）。
    # 欄位最小化（隱私）：不整包送敏感資料，只送投影所需摘要。
    try:
        from core.event_bus import TOPIC_WORKORDER_LIFECYCLE, publish_event
        await publish_event(
            TOPIC_WORKORDER_LIFECYCLE,
            {
                "tenant_id": tenant_id,
                "work_order_id": wo_id,
                "status": order.get("status"),
                "event_type": event_type,
                "technician_id": order.get("technician_id"),
                "document_number": order.get("document_number"),
                "district": order.get("district"),
                "scheduled_time": order.get("scheduled_time"),
                "occurred_at": order.get("updated_at"),
            },
            key=wo_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("event publish work_order lifecycle failed (non-fatal)")
    return order


async def _auto_notify(
    tenant_id: str, user_id, ntype: str, title: str, body: str = "",
    wo_id: str | None = None,
) -> None:
    """CR-0062：事件驅動自動通知（best-effort 非致命；user_id 缺則略過）。

    把生命週期事件接到通知中心自動產生（原通知只能手動 push）。
    UAT-0718 W5-3（已釘契約）：wo_id 給定時帶 related_entity
    {"type":"work_order","id":"<uuid>","url":"/work-orders/<uuid>"}——前端依
    related_entity.url 渲染可點跳轉。既有歷史通知不回填（僅新通知帶欄位）。
    """
    if not user_id:
        return
    try:
        from services import notification_service
        req: dict = {
            "target_type": "user", "target_id": str(user_id),
            "type": ntype, "title": title, "body": body,
        }
        if wo_id:
            req["related_entity"] = {
                "type": "work_order", "id": str(wo_id),
                "url": f"/work-orders/{wo_id}",
            }
        await notification_service.push_notification(req, tenant_id=tenant_id)
    except Exception:  # noqa: BLE001
        logger.exception("auto-notify failed (non-fatal)")


async def _publish_pool_change(
    *,
    tenant_id: str,
    wo_id: str,
    technician_id: str,
    event: str,  # "added" / "taken" / "cancelled"
) -> None:
    """推 `/realtime/pool/{technician_id}` event 對齊前端 pool/page.tsx 契約。

    前端 useRealtimeChannel 期待 payload:
      - added: 帶完整 work_order 物件（prepend 到列表）
      - taken: 帶 work_order_id（從列表移除）
      - cancelled: 帶 work_order_id（從列表移除）
    """
    if not technician_id:
        return
    try:
        from realtime.ws_hub import hub

        payload: dict = {"event": event, "work_order_id": wo_id}
        if event == "added":
            # added 需帶完整 wo 物件供 prepend；pool 頻道屬接單前視角
            # → 套 UAT P1-4 隱私遮蔽（不推客戶姓名/電話/完整地址）
            try:
                payload["work_order"] = _mask_pool_privacy(await get_order(
                    tenant_id=tenant_id, wo_id=wo_id,
                ))
            except Exception:  # noqa: BLE001
                logger.exception("get_order failed for pool publish added")
        await hub.publish(
            f"/realtime/pool/{technician_id}",
            {
                "type": f"work_order.pool_{event}",
                "payload": payload,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "ws publish pool/%s event=%s failed (non-fatal)",
            technician_id[:8] if technician_id else "?", event,
        )


# ── CR-0193 工單事件唯一寫入出口（migration 122）────────────────────────────
# 這是全專案寫 work_order_events 的**唯一**入口，不要繞過它直接 INSERT。
#
# WHY 唯一出口：seq 是 per-工單連號，用途是「缺號即代表事件遺失」（TC-WO-01
# 要的「事件溯源」）。任何一條繞過取號的寫入都會在連號上開洞，缺號就再也無法
# 區分「被刪」與「那條路徑沒編號」，溯源價值歸零。DB 端已用 NOT NULL 兜底
# （不給 seq 直接寫不進去），這裡是正向的取號實作。
#
# WHY 不用 advisory lock：core/db.py 是 autocommit=True 的**共用單一連線**，
# xact lock 會立刻釋放（無交易可綁），改用 session lock 則漏釋放就卡死整條連線。
# 改走「單語句取號 + UNIQUE 擋碰撞 + 重試」——autocommit 下失敗語句不會讓
# 交易進入 aborted 狀態，所以重試是乾淨的。
_EVENT_SEQ_MAX_ATTEMPTS = 5


async def _insert_wo_event(
    *,
    wo_id: str,
    tenant_id: str,
    event_type: str,
    payload: dict | None = None,
    actor_user_id: str | None = None,
) -> None:
    """寫一筆 work_order_events，seq 於同一語句內取 per-工單連號。

    event_type 必須是 migration 122 CHECK 清單內的值，否則 CheckViolation。
    新增 event_type 一律要同步改該 CHECK（這是第 5 次同類 migration 的由來）。
    """
    from psycopg import errors as _pg_errors

    sql = (
        "INSERT INTO work_order_events "
        "  (work_order_id, tenant_id, actor_user_id, event_type, payload, seq) "
        "SELECT %s::uuid, %s::uuid, %s, %s, %s::jsonb, COALESCE(MAX(seq), 0) + 1 "
        "FROM work_order_events WHERE work_order_id = %s::uuid"
    )
    params = (
        wo_id,
        tenant_id,
        actor_user_id,
        event_type,
        json.dumps(payload or {}, ensure_ascii=False),
        wo_id,
    )
    for attempt in range(_EVENT_SEQ_MAX_ATTEMPTS):
        try:
            await db_module._conn.execute(sql, params)
            return
        except _pg_errors.UniqueViolation as exc:
            # 只吞「同工單併發撞號」；其他 UNIQUE 衝突照原樣拋出，不掩蓋真 bug。
            constraint = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint != "work_order_events_wo_seq_key":
                raise
            if attempt == _EVENT_SEQ_MAX_ATTEMPTS - 1:
                logger.error(
                    "work_order_events 取號重試 %d 次仍撞號 wo=%s event=%s",
                    _EVENT_SEQ_MAX_ATTEMPTS, wo_id, event_type,
                )
                raise


async def _fetch_status_for_update(wo_id: str, tenant_id: str) -> str:
    """讀取當前 status（含 tenant 守衛），查不到就 404。

    ⚠️ **名字裡的 `for_update` 是歷史遺留，這裡沒有列鎖，也不可能有。**
    本專案的連線是 autocommit、無顯式交易，`FOR UPDATE` 的鎖不跨語句
    （見 CR-0199 §3.2 與本檔 L607 的 UAT R3-6 註解）。

    因此**呼叫端若要依據回傳值做寫入，UPDATE 必須自己帶樂觀條件**——
    用 `_assert_transition_applied()` 檢查 rowcount，不要假設狀態在期間沒被改動。
    """
    cur = await db_module._conn.execute(
        f"SELECT wo.status {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    return row[0]


def _assert_transition_applied(cur, *, allowed: set[str], action: str) -> None:
    """樂觀鎖檢查（CR-0199 方案 A）：UPDATE 沒中任何列 = 狀態已離開允許集合。

    搭配 `WHERE ... AND status = ANY(%s)` 使用，參數傳 `sorted(_XXX_FROM)`。

    ## 為什麼綁「允許集合」而不是「剛才讀到的那個值」

    直覺會想寫 `AND status = %s` 帶 `current`，但那**會誤擋合法操作**——
    當允許集合有多個值時，status 在集合內的合法變動會讓 rowcount 變 0。

    實例（`complete_order`，`_COMPLETE_FROM = {accepted, in_progress}`）：
    技師讀到 `accepted` 後要跑完整完工硬閘（多次 config 讀取與 DB 查詢，百毫秒級），
    期間客戶在公開連結核可了範圍變更，`scope_change_service` 把狀態推進到
    `in_progress`——那是合法轉移，且 `in_progress` 本來就是合法的完工來源。
    若綁快照值，技師傳完照片與簽名後會收到 409 並被迫重送整包。

    綁集合則與前置檢查 `if current not in _XXX_FROM: raise 409` **語意完全等價**，
    因此不可能比既有檢查更嚴：rowcount == 0 只剩兩種成因——狀態被改到集合之外
    （正是要擋的競態），或該列被刪除。

    註：`sorted()` 是必要的，psycopg3 不會轉換 `set`。`work_orders.status` 是
    VARCHAR(50) 而非 enum，所以 `varchar = ANY(text[])` 可解析。
    """
    if cur.rowcount == 0:
        raise ApiError(
            "STATE_CONFLICT",
            f"工單狀態已被其他操作變更（{action}需要狀態為 {'、'.join(sorted(allowed))}），"
            "請重新載入後再試",
            409,
        )


async def accept_order(
    *,
    tenant_id: str,
    wo_id: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> dict:
    """接單：assigned → accepted；技師搶單 created → accepted（claim 寫入 technician_id）。

    行為矩陣（依呼叫者角色 × 工單狀態）：
      - 技師 × created            → 搶單 claim：technician_id = 自己 + accepted
      - 技師 × assigned（給自己）  → 正常接單（FR-0005）
      - 技師 × assigned（給他人）  → 409（FR-0005 A9 已派他人）
      - 非技師 × assigned          → 代操作接單（後台，維持原行為）
      - 非技師 × created           → 409（created 需 assign 或由技師搶單）
    技師 technicians.status != active → 403（BR-M07-01 阻擋派工）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    tech_ctx: dict | None = None
    if actor_role == "technician":
        tech_ctx = await _fetch_technician_for_user(actor_user_id)
        if not tech_ctx or tech_ctx["status"] != "active":
            raise ApiError(
                "TECHNICIAN_NOT_DISPATCHABLE",
                "技師目前狀態不可接單（需 active — BR-M07-01）",
                403,
            )

    current = await _fetch_status_for_update(wo_id, tenant_id)
    allowed_from = {"created", "assigned"} if tech_ctx else _ACCEPT_FROM
    if current not in allowed_from:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot accept work order in status '{current}'; expected one of {sorted(allowed_from)}",
            409,
        )
    # 取 technician_id 給 pool publish + claim 判斷
    cur = await db_module._conn.execute(
        "SELECT technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    tech_row = await cur.fetchone()
    tech_id = str(tech_row[0]) if tech_row and tech_row[0] else None

    if tech_ctx and tech_id and tech_id != tech_ctx["id"]:
        # FR-0005 §1.2 A9：已派給其他技師
        raise ApiError(
            "STATE_CONFLICT",
            "該案已指派給其他技師",
            409,
        )
    claim_tech_id = tech_ctx["id"] if tech_ctx and not tech_id else None
    if claim_tech_id:
        tech_id = claim_tech_id
        # CR-0114 R4：搶單寫入 technician_id 前確保投影存在（登入技師通常已投影,
        # 此為防禦;fallback no-op）
        from core.tech_mirror import ensure_technician_projection
        await ensure_technician_projection(claim_tech_id)

    # CR-0199：樂觀條件必須綁**上面那個動態的** allowed_from，不是常數 _ACCEPT_FROM——
    # 技師搶單走 created → accepted（tech_ctx 存在時 allowed_from 含 'created'），
    # 綁死 _ACCEPT_FROM={assigned} 會讓搶單全部 409。
    _cur = await db_module._conn.execute(
        # CR-0043 Tier②：技師接單後完工細狀態進「待完工回報」（M05 Q052 起點）
        "UPDATE work_orders SET status = 'accepted', accepted_at = NOW(), "
        "  technician_id = COALESCE(%s::uuid, technician_id), "
        "  completion_status = 'pending_report', updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (claim_tech_id, wo_id, sorted(allowed_from)),
    )
    _assert_transition_applied(_cur, allowed=allowed_from, action="接單")
    # CR-0193：生命週期事件（原本 accept 不落事件流 → timeline 看不到「接單」）
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="accepted",
        payload={
            "technician_id": tech_id,
            "from_status": current,
            "claimed": bool(claim_tech_id),  # True = 從公開池搶單，非小編指派
        },
    )
    # event=taken 從技師個人 pool 列表移除（已進 my-orders）
    if tech_id:
        await _publish_pool_change(
            tenant_id=tenant_id, wo_id=wo_id, technician_id=tech_id,
            event="taken",
        )
    # CR-0028 斷點 3 — 技師接單推 LINE 給客戶（best-effort，複用 CR-0017 outbox）
    try:
        from services import line_push_outbox_service
        doc_cur = await db_module._conn.execute(
            "SELECT document_number FROM work_orders WHERE id = %s::uuid", (wo_id,)
        )
        doc_row = await doc_cur.fetchone()
        await line_push_outbox_service.enqueue(
            tenant_id=tenant_id,
            push_kind="work_order_accepted",
            payload={
                "work_order_id": wo_id,
                "document_number": doc_row[0] if doc_row else None,
            },
            reference_id=wo_id,
            reference_table="work_orders",
        )
    except Exception:  # noqa: BLE001
        logger.exception("outbox enqueue work_order_accepted failed (non-fatal)")
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.accepted"
    )


async def reject_order(
    *,
    tenant_id: str,
    wo_id: str,
    reason: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> dict:
    """技師拒單（CR-0166 R1 / UF-04 / TC-DISPATCH-02）：assigned → created 回池。

    技師本人才能拒本人被派的單；拒單後清 technician_id、回 'created'（全技師 pool
    可搶、小編可重派），寫 dispatch_logs(action='reject')＋work_order_events＋通知小編。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    reason = (reason or "").strip()
    if len(reason) < 2:
        raise ApiError("VALIDATION_ERROR", "拒單原因必填（至少 2 字）", 422)

    tech_ctx = await _fetch_technician_for_user(actor_user_id)
    if not tech_ctx:
        raise ApiError("TECHNICIAN_NOT_FOUND", "找不到對應技師帳號", 404)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _REJECT_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reject work order in status '{current}'; expected one of {sorted(_REJECT_FROM)}",
            409,
        )
    cur = await db_module._conn.execute(
        "SELECT technician_id, created_by FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    tech_id = str(row[0]) if row and row[0] else None
    created_by = str(row[1]) if row and row[1] else None
    if tech_id != tech_ctx["id"]:
        raise ApiError("STATE_CONFLICT", "只能拒絕指派給本人的工單", 409)

    note = f"[REJECTED] {tech_ctx['id']}: {reason}"
    # CR-0199：樂觀條件——避免把「已被取消/已被他人改派」的單打回派工池
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET status = 'created', technician_id = NULL, "
        "  status_reason = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (reason, wo_id, sorted(_REJECT_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_REJECT_FROM, action="拒單")
    await db_module._conn.execute(
        "INSERT INTO dispatch_logs (work_order_id, action, technician_id, rejection_reason, notes) "
        "VALUES (%s::uuid, 'reject', %s::uuid, %s, %s)",
        (wo_id, tech_ctx["id"], reason, note),
    )
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="reject",
        payload={"technician_id": tech_ctx["id"], "reason": reason, "from_status": current},
    )
    # 拒單技師個人 pool 列表移除該單（已回無主 created，非其負責）
    await _publish_pool_change(
        tenant_id=tenant_id, wo_id=wo_id, technician_id=tech_ctx["id"], event="taken",
    )
    # 通知派工小編（best-effort）＋稽核
    try:
        if created_by:
            await _auto_notify(
                tenant_id, created_by, "work_order_rejected",
                "技師拒接工單", f"工單已被技師退回派工池，原因：{reason}",
                wo_id=wo_id,
            )
        from services import audit_log_service
        await audit_log_service.log_event(
            event_type="dispatch_decision", actor_id=actor_user_id, actor_role=actor_role,
            action="technician_reject", target_type="work_order", target_id=wo_id,
            payload={"technician_id": tech_ctx["id"], "reason": reason},
        )
    except Exception:  # noqa: BLE001
        logger.exception("reject_order notify/audit failed (non-fatal)")
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.rejected"
    )


async def _unescalate_linked_conversation(*, tenant_id: str, wo_id: str) -> None:
    """工單結案連動：把關聯對話從 escalated 交還 AI（CR-0024 Phase 1，D2-b）。

    鏈：work_order.problem_card_id → problem_cards.conversation_id。
    **fail-soft**：找不到鏈、對話非 escalated、或任何錯誤都只 log，絕不阻斷工單結案。
    """
    try:
        cur = await db_module._conn.execute(
            "SELECT pc.conversation_id FROM work_orders wo "
            "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
            "WHERE wo.id = %s::uuid AND pc.conversation_id IS NOT NULL",
            (wo_id,),
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return
        upd = await db_module._conn.execute(
            "UPDATE conversations SET status = 'active', updated_at = NOW() "
            "WHERE id = %s::uuid AND status = 'escalated'",
            (str(row[0]),),
        )
        if getattr(upd, "rowcount", 0):
            logger.info(
                "WO 結案連動交還 AI: wo=%s conv=%s escalated→active",
                wo_id[:8], str(row[0])[:8],
            )
    except Exception:  # noqa: BLE001 — 連動失敗不可阻斷結案
        logger.warning("WO 結案連動交還對話失敗 (wo=%s)", wo_id, exc_info=True)


# ── CR-0039 完工硬閘（BR-M08-03，業主裁決 §8；門檻入 M18 config completion_policy，不寫死）──
_COMPLETION_POLICY_DEFAULTS = {
    "min_photos": 3,
    "require_signature": True,
    "serial_required_categories": ["install"],
    "allow_supervisor_override": True,
    # CR-0043 Tier④：完工前是否強制三段免責同意（預設 off 避免回歸破壞；config 開才擋）
    "require_consents": False,
}

# CR-0043 Tier④：三段免責同意（對 PDF §4 / consent_service CONSENT_TEXTS）
_REQUIRED_CONSENTS = ("new_installation", "lock_destruction", "personal_data")


async def _consents_satisfied(wo_id: str) -> bool:
    """三段免責是否皆已 accepted（work_order_consents）。"""
    cur = await db_module._conn.execute(
        "SELECT consent_type FROM work_order_consents "
        "WHERE work_order_id = %s::uuid AND accepted = TRUE",
        (wo_id,),
    )
    rows = await cur.fetchall()
    accepted = {r[0] for r in rows}
    return all(c in accepted for c in _REQUIRED_CONSENTS)


async def _has_pending_scope_change(wo_id: str) -> bool:
    """CR-0049 / BR-M08-02：是否有未決（status='pending'）範圍變更（報價/加價未經客戶確認）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM scope_changes WHERE work_order_id = %s::uuid AND status = 'pending' LIMIT 1",
        (wo_id,),
    )
    return await cur.fetchone() is not None


async def _signature_exists(wo_id: str) -> bool:
    """完工是否已有客戶簽名（digital_signatures；CR-0039 HD-4 驗證簽名真存在，非僅非空字串）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM digital_signatures "
        "WHERE document_type = 'work_order' AND document_id = %s::uuid "
        "  AND signer_role = 'customer' LIMIT 1",
        (wo_id,),
    )
    return (await cur.fetchone()) is not None


async def _start_retrospective_audit_timer(wo_id: str) -> None:
    """急件單完工回報時為補審報價起算 4h 窗（CR-0129 / 15_SDS §4.5 步驟3）。

    僅急件單（PC.emergency_class 非空）且補審尚未完成（retrospective_audit_only
    或已送客戶）且未起算者；非急件單無此類報價，天然 no-op。
    """
    from services import config_m18_service

    hours = 4
    cfg = await config_m18_service.read_global_value(namespace="emergency_audit_policy")
    if isinstance(cfg, dict):
        try:
            hours = int(cfg.get("audit_window_hours", 4))
        except (TypeError, ValueError):
            pass
    cur = await db_module._conn.execute(
        "UPDATE quote q SET audit_due_at = NOW() + (INTERVAL '1 hour' * %s), updated_at = NOW() "
        "FROM work_orders wo JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "WHERE q.work_order_id = wo.id AND wo.id = %s::uuid "
        "  AND pc.emergency_class IS NOT NULL "
        "  AND q.audit_due_at IS NULL "
        "  AND q.state IN ('retrospective_audit_only', 'sent')",
        (hours, wo_id),
    )
    if cur.rowcount:
        logger.info("急件補審窗起算：wo=%s quotes=%d due=+%dh", wo_id, cur.rowcount, hours)


async def _enforce_completion_gate(
    *,
    wo_id: str,
    summary: str,
    photo_evidence_ids: list[str] | None,
    signature_evidence_id: str | None,
    is_override: bool,
    override_reason: str | None,
    actor_role: str | None,
) -> str:
    """CR-0039 完工硬閘。回傳（override 時加稽核註記的）summary；違反任一閘 → 422。

    門檻讀 M18 config completion_policy（缺失 fallback 預設）。
    is_override（admin/dispatcher 走 :complete）跳過證據閘，但須填 reason 並留稽核註記（HD-2）。
    """
    from services import config_m18_service

    policy = dict(_COMPLETION_POLICY_DEFAULTS)
    cfg = await config_m18_service.read_global_value(namespace="completion_policy")
    if isinstance(cfg, dict):
        policy.update(cfg)

    if is_override:
        if not policy.get("allow_supervisor_override", True):
            raise ApiError("OVERRIDE_NOT_ALLOWED", "完工 override 已停用", 403)
        if not (override_reason and override_reason.strip()):
            raise ApiError("VALIDATION_ERROR", "主管 override 完工必須填寫原因", 422)
        return (
            f"[COMPLETE_OVERRIDE by {actor_role or 'supervisor'}: "
            f"{override_reason.strip()[:300]}] {summary}"
        )

    # 技師正規完工 — 三道硬閘
    min_photos = int(policy.get("min_photos", 3))
    n_photos = len(photo_evidence_ids or [])
    if n_photos < min_photos:
        raise ApiError(
            "INSUFFICIENT_PHOTOS",
            f"完工照片至少 {min_photos} 張（目前 {n_photos} 張）",
            422,
        )
    if policy.get("require_signature", True):
        if not signature_evidence_id or not await _signature_exists(wo_id):
            raise ApiError("SIGNATURE_REQUIRED", "完工需客戶簽名（簽名紀錄不存在）", 422)
    serial_cats = policy.get("serial_required_categories") or []
    if serial_cats:
        cur = await db_module._conn.execute(
            "SELECT service_category, serial_number FROM work_orders WHERE id = %s::uuid",
            (wo_id,),
        )
        row = await cur.fetchone()
        svc_cat, serial = (row[0], row[1]) if row else (None, None)
        if svc_cat in serial_cats and not (serial and str(serial).strip()):
            raise ApiError(
                "SERIAL_REQUIRED",
                "此安裝案需登錄鎖體序號才可完工（BR-M10-03）",
                422,
            )
    # CR-0043 Tier④：三段免責 gate（config require_consents 開才擋；PDF §4 / 法律合規）
    if policy.get("require_consents", False):
        if not await _consents_satisfied(wo_id):
            raise ApiError(
                "CONSENTS_REQUIRED",
                "完工前須完成三段免責同意（新機安裝/破壞鎖/個資）",
                422,
            )
    # CR-0049 / BR-M08-02：報價變更未經客戶確認（pending scope）→ 不可完工（安全閘，admin override 路徑可繞）
    if await _has_pending_scope_change(wo_id):
        raise ApiError(
            "PENDING_SCOPE_CHANGE",
            "有未經客戶確認的範圍/加價變更，須客戶確認或主管覆寫後才可完工",
            409,
        )
    # CR-0064 / TI-M05-02 / BR-M05：結案前服務地址必填（電子工單/派工依據）
    acur = await db_module._conn.execute(
        "SELECT customer_address, quote_gate_applied FROM work_orders WHERE id = %s::uuid", (wo_id,))
    arow = await acur.fetchone()
    # ADR-015②：地址須為「有效值」——非空且達最小長度，擋「.」「x」「-」等佔位字元繞過硬閘
    _MIN_CLOSE_ADDRESS_LENGTH = 6
    _addr = str(arow[0]).strip() if (arow and arow[0]) else ""
    if len(_addr) < _MIN_CLOSE_ADDRESS_LENGTH:
        raise ApiError("ADDRESS_REQUIRED_FOR_CLOSE", "結案前須有有效服務地址（至少 6 字）", 422)
    # CR-0128/CR-0129（D2a）：完工閘報價分支——標準單須 accepted；**急件補審中可完工**
    # （retrospective_audit_only 佔位或補審已送客戶 audit_due_at 非空）——完工回報是
    # 4h 補審窗起算點（15_SDS §4.5），補審完成擋在結案（confirm_order）。
    # 僅驗 gate 後新單（quote_gate_applied=TRUE）；存量單豁免（D3a）。
    if arow and bool(arow[1]):
        qcur = await db_module._conn.execute(
            "SELECT 1 FROM quote WHERE work_order_id = %s::uuid "
            "  AND (state = 'accepted' OR state = 'retrospective_audit_only' "
            "       OR audit_due_at IS NOT NULL) LIMIT 1",
            (wo_id,),
        )
        if not await qcur.fetchone():
            raise ApiError(
                "QUOTE_NOT_CONFIRMED_FOR_CLOSE",
                "完工前報價須經客戶確認（急件單須有補審佔位報價）——BR-WO-01/ADR-015②",
                422,
            )
    return summary


# ── CR-0169 師傅 LINE 推播(平台官方號)──────────────────────────────────────
# 品牌 api 不碰平台 LINE 憑證:派單/建池單後 service-to-service 呼叫 tech api
# internal 端點(TECH_API_BASE_URL+INTERNAL_API_TOKEN env-gated;未配置=no-op)。
# fail-soft:推播失敗絕不阻斷派單主流程(網頁通知中心照舊為保底)。

def _tech_service_auth() -> tuple[str | None, dict[str, str]]:
    """新 service credential 優先；migration 期間才退回 shared token。"""
    credential = (os.getenv("TECH_API_SERVICE_CREDENTIAL") or "").strip()
    if credential:
        return credential, {"X-Service-Credential": credential}
    legacy = (os.getenv("INTERNAL_API_TOKEN") or "").strip()
    return (legacy or None), ({"X-Internal-Token": legacy} if legacy else {})


def _tech_line_wo_summary(wo: dict) -> dict:
    """推播內容最小化(CIA §4):區域+品牌型號+單號,絕不含客戶姓名/地址/電話。
    priority 供 outbox lag 分級 SLO（FR-API-05b：急件≤15s），非 PII。"""
    return {
        "id": wo.get("id"),
        "document_number": wo.get("document_number"),
        "district": wo.get("district"),
        "brand": wo.get("brand"),
        "model": wo.get("model"),
        "priority": wo.get("priority"),
    }


async def _notify_tech_line(path: str, payload: dict) -> None:
    # strip:secret 建立時常帶尾端換行,aiohttp 嚴格模式會拒發(0719 雲端 UAT C-5
    # header injection 防護炸推播);收端 deps.py:require_internal_token 本就 strip。
    base = (os.getenv("TECH_API_BASE_URL") or "").strip()
    auth_value, auth_headers = _tech_service_auth()
    if not base or not auth_value:
        logger.warning(
            "tech LINE notify 未配置(缺 TECH_API_BASE_URL/TECH_API_SERVICE_CREDENTIAL"
            " 或 migration fallback)→ 跳過推播 path=%s",
            path,
        )
        return  # 未配置=跳過(本機單 stack / 測試環境)
    try:
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            await session.post(
                f"{base.rstrip('/')}{path}",
                json=payload,
                headers=auth_headers,
            )
    except Exception:  # noqa: BLE001 — fail-soft,不阻斷主流程
        logger.warning("tech LINE notify 失敗(non-fatal)path=%s", path, exc_info=True)


def _tech_dispatch_via_outbox() -> bool:
    """CR-0172 HD-F 灰度旗標:技師派工推播是否走 outbox(送達保證)。預設 false(走舊
    同步 HTTP,行為與現況一致);穩定後可移除舊路徑(§9 S6)。"""
    return os.getenv("TECH_DISPATCH_VIA_OUTBOX") == "1"


async def _dispatch_tech_notify(
    *, tenant_id: str, wo_id: str, technician_id: str, wo_summary: dict,
) -> None:
    """CR-0172:技師派工指派推播——flag 開啟走 outbox(enqueue → worker 投 tech-portal
    內部端點,取得送達保證,閉合 R10);關閉走舊同步 HTTP。兩者皆 fail-soft,絕不阻斷
    派單主流程(HD-3 指派必推的可靠性由 outbox 重試/dead 提供)。
    """
    payload = {
        "tenant_id": tenant_id,
        "technician_id": technician_id,
        "work_order": wo_summary,
    }
    if _tech_dispatch_via_outbox():
        try:
            from services import line_push_outbox_service
            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id, push_kind="tech_dispatch_assigned",
                payload=payload, reference_id=wo_id, reference_table="work_orders",
            )
        except Exception:  # noqa: BLE001 — enqueue 失敗 non-fatal
            logger.exception("tech dispatch enqueue 失敗(non-fatal)wo=%s", wo_id)
    else:
        await _notify_tech_line("/api/v1/internal/technicians/notify-assign", payload)


# v2 完工送簽 summary 的機器格式（work_orders_v2.onsite_completion_v2 組裝）：
#   [ONSITE_COMPLETE] sig=<evidence_id> photos=[<id>,<id>,...] notes=<自由文字到行尾>
_ONSITE_SUMMARY_RE = re.compile(
    r"^\[ONSITE_COMPLETE\]\s+sig=\S+\s+photos=\[[^\]]*\](?:\s+notes=(?P<notes>[\s\S]*))?$"
)


def _extract_clean_summary(summary: str | None) -> str | None:
    """completion_summary 的乾淨化（CR-0100 B0「技師 notes 抽出」）。

    機器格式 → 只留 notes 人話（無 notes → None，前端顯示「無施工摘要」）；
    非機器格式（admin :complete override 的自由文字等）→ 原樣保留。
    """
    if not summary or not summary.strip():
        return None
    s = summary.strip()
    m = _ONSITE_SUMMARY_RE.match(s)
    if m:
        notes = (m.group("notes") or "").strip()
        return notes or None
    return s


async def complete_order(
    *,
    tenant_id: str,
    wo_id: str,
    summary: str,
    actual_amount: str | None = None,
    photo_evidence_ids: list[str] | None = None,
    signature_evidence_id: str | None = None,
    is_override: bool = False,
    override_reason: str | None = None,
    actor_role: str | None = None,
    teaching_note: str | None = None,
    materials_used: str | None = None,
    payment_proof: str | None = None,
    function_tests: list | None = None,
    # CR-0193：生命週期事件要記「誰做的」。此前 complete/cancel/escalate/confirm
    # 的 actor 沒有任何結構化留痕（_audit_action 只覆蓋 reschedule/delay 三個動作）。
    actor_user_id: str | None = None,
) -> dict:
    """accepted | in_progress → completed, set completed_at = NOW (auto-fill started_at).

    CR-0039 完工硬閘（BR-M08-03）：技師正規完工強制 照片≥config / 客戶簽名存在 / 安裝案序號；
    admin/dispatcher 走 :complete 為 is_override 路徑（記 reason、跳過證據閘）。門檻入 M18 config。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _COMPLETE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot complete work order in status '{current}'; expected one of {sorted(_COMPLETE_FROM)}",
            409,
        )
    # CR-0100 B0：completion_summary 應存「技師 notes 抽出」的人話（models.generated 欄位描述）。
    # v2 完工送簽的 summary 是機器字串（[ONSITE_COMPLETE] sig=.. photos=[..] notes=..，稽核用，
    # 原樣落 service_report）——此處抽出 notes 落 completion_summary；自由文字（admin override 等）原樣。
    clean_summary = _extract_clean_summary(summary)
    # CR-0041 / BR-M15-03：high_risk_hold 擋完工（含 override，須先 resolve 異常解除 hold）
    await _assert_not_high_risk_hold(wo_id)
    # CR-0039 完工硬閘 — 通過回（可能被 override 註記的）summary，違反 → 422
    summary = await _enforce_completion_gate(
        wo_id=wo_id,
        summary=summary,
        photo_evidence_ids=photo_evidence_ids,
        signature_evidence_id=signature_evidence_id,
        is_override=is_override,
        override_reason=override_reason,
        actor_role=actor_role,
    )
    # CR-0058 / BR-M08-03 完工套件 ④⑤：用料 + 付款證明（config 開才硬擋；技師正規路徑）
    if not is_override:
        from services import config_m18_service
        cpol = await config_m18_service.read_global_value(namespace="completion_policy") or {}
        if cpol.get("require_materials") and not (materials_used and materials_used.strip()):
            raise ApiError("MATERIALS_REQUIRED", "完工須登錄現場用料（completion_policy.require_materials）", 422)
        if cpol.get("require_payment_proof") and not (payment_proof and payment_proof.strip()):
            raise ApiError("PAYMENT_PROOF_REQUIRED", "完工須登錄付款證明（completion_policy.require_payment_proof）", 422)

    final_price: float | None = None
    if actual_amount is not None:
        try:
            final_price = float(actual_amount)
        except ValueError as e:
            raise ApiError("VALIDATION_ERROR", "actual_amount is not a valid decimal", 422) from e
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'completed', "
        "  completed_at = NOW(), "
        "  started_at = COALESCE(started_at, NOW()), "
        "  service_report = %s, "
        "  final_price = COALESCE(%s, final_price), "
        # CR-0043 Tier②：技師完工回報+照片+簽名後，完工細狀態進「待客戶確認」（M05 Q052）
        "  completion_status = 'pending_customer_confirm', "
        # CR-0050 教學 + CR-0058 用料/付款證明（完工套件；空則保留既有）
        "  teaching_note = COALESCE(%s, teaching_note), "
        "  materials_used = COALESCE(%s, materials_used), "
        "  payment_proof = COALESCE(%s, payment_proof), "
        # CR-0100：完工乾淨摘要（B0）+ 功能測試逐項結果（B1；空則保留既有）
        "  completion_summary = COALESCE(%s, completion_summary), "
        "  function_tests = COALESCE(%s::jsonb, function_tests), "
        "  updated_at = NOW() "
        # CR-0199：樂觀條件——完工不可覆蓋期間被取消的單。綁「允許集合」而非讀到的
        # 快照值：客戶核可範圍變更會把 accepted 合法推進到 in_progress，兩者都可完工
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (summary, final_price,
         (teaching_note.strip() if teaching_note and teaching_note.strip() else None),
         (materials_used.strip() if materials_used and materials_used.strip() else None),
         (payment_proof.strip() if payment_proof and payment_proof.strip() else None),
         clean_summary,
         (json.dumps(function_tests) if function_tests else None),
         wo_id, sorted(_COMPLETE_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_COMPLETE_FROM, action="完工回報")
    # CR-0129 / 15_SDS §4.5：急件單完工回報＝補審 4h 窗起算——佔位/已送補審報價寫
    # audit_due_at（窗長讀 M18 config emergency_audit_policy.audit_window_hours，缺省 4h）。
    # fail-soft：起算失敗記 ERROR（可告警人工補），不阻斷完工。
    try:
        await _start_retrospective_audit_timer(wo_id)
    except Exception:  # noqa: BLE001 — timer 起算失敗不可卡死完工主流程
        logger.exception("急件補審 timer 起算失敗（需人工補 audit_due_at）wo=%s", wo_id)

    # CR-0117 S3：完工落庫後回寫技師聚合統計（fail-soft）
    await _rollup_tech_stats_safe(tenant_id, wo_id)
    await _unescalate_linked_conversation(tenant_id=tenant_id, wo_id=wo_id)
    # CR-0027：完工推 LINE 給客戶（電子工單已開立 + 最終金額，只露對外價）。best-effort。
    try:
        from services import line_push_outbox_service
        dcur = await db_module._conn.execute(
            "SELECT document_number, customer_final_amount FROM work_orders WHERE id = %s::uuid",
            (wo_id,),
        )
        drow = await dcur.fetchone()
        await line_push_outbox_service.enqueue(
            tenant_id=tenant_id,
            push_kind="work_order_document",
            payload={
                "work_order_id": wo_id,
                "document_number": drow[0] if drow else None,
                "final_amount": (f"{float(drow[1]):,.0f}" if drow and drow[1] is not None else None),
            },
            reference_id=wo_id,
            reference_table="work_orders",
        )
    except Exception:  # noqa: BLE001
        logger.exception("outbox enqueue work_order_document failed (non-fatal)")
    # CR-0056：完工結案 Email 通道（PDF §四 三聯數位化「結案發 PDF 至 Email/LINE」；LINE 已有）。
    # best-effort：SMTP 未配置時 send_email 回 False 不丟例外；客戶無 email 則略過。
    try:
        import asyncio
        from services import email_provider
        ecur = await db_module._conn.execute(
            "SELECT u.email, wo.document_number FROM work_orders wo "
            "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
            "LEFT JOIN conversations c ON pc.conversation_id = c.id "
            "JOIN users u ON c.user_id = u.id WHERE wo.id = %s::uuid",
            (wo_id,),
        )
        erow = await ecur.fetchone()
        cust_email = (erow[0] if erow else None) or None
        if cust_email:
            doc_no = (erow[1] if erow else None) or wo_id
            await asyncio.to_thread(
                email_provider.send_email,
                to=cust_email,
                subject=f"您的服務已完工（工單 {doc_no}）",
                body_text=(
                    f"您好，您的智慧鎖服務已完工。工單編號：{doc_no}。\n"
                    "電子工單與費用明細請見 LINE 通知或洽客服。感謝您的支持。"
                ),
            )
    except Exception:  # noqa: BLE001
        logger.exception("completion email failed (non-fatal)")
    # CR-0062：事件驅動通知 — 通知開單者（客服/管理）工單已完工待審核
    try:
        ccur = await db_module._conn.execute(
            "SELECT created_by, document_number FROM work_orders WHERE id = %s::uuid", (wo_id,))
        crow = await ccur.fetchone()
        if crow and crow[0]:
            await _auto_notify(
                tenant_id, crow[0], "work_order_completed",
                f"工單 {crow[1] or wo_id} 已完工",
                "技師已回報完工，待客服/客戶確認結案。",
                wo_id=wo_id,
            )
    except Exception:  # noqa: BLE001
        logger.exception("completion auto-notify failed (non-fatal)")
    # CR-0193：生命週期事件（原本 complete 不落事件流 → timeline 看不到「完工」，
    # 而 evidence_package_service 正是拿事件流當爭議舉證來源）
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="completed",
        payload={
            "from_status": current,
            "actor_role": actor_role,
            "is_override": is_override,       # True = 後台代為結案，非技師現場送簽
            "override_reason": override_reason,
            "actual_amount": actual_amount,
        },
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.completed"
    )


async def cancel_order(
    *,
    tenant_id: str,
    wo_id: str,
    reason: str | None = None,
    actor_user_id: str | None = None,  # CR-0193 生命週期事件 actor
) -> dict:
    """created | assigned | accepted | in_progress → cancelled."""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _CANCEL_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot cancel work order in status '{current}'; expected non-terminal",
            409,
        )
    # CR-0026 / BR-M05-01：取消必填原因（status_reason gate）
    if not reason or not reason.strip():
        raise ApiError(
            "VALIDATION_ERROR",
            "取消工單必須填寫原因（status_reason 必填，BR-M05-01）",
            422,
        )
    # 取 technician_id 給 pool publish (若已派)
    cur = await db_module._conn.execute(
        "SELECT technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    tech_row = await cur.fetchone()
    tech_id = str(tech_row[0]) if tech_row and tech_row[0] else None
    # 寫入結構化 status_reason 欄（同步保留 service_report 字串軌跡）
    # CR-0199：樂觀條件——最嚴重的一組是「取消 vs 完工」，完工是計酬依據，不可被覆寫
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'cancelled', "
        "  status_reason = %s, "
        "  service_report = COALESCE(service_report, '') || E'\\n[CANCELLED] ' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (reason, reason, wo_id, sorted(_CANCEL_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_CANCEL_FROM, action="取消")
    # event=cancelled 把該 tech pool 該 wo 移除（若已派）
    if tech_id:
        await _publish_pool_change(
            tenant_id=tenant_id, wo_id=wo_id, technician_id=tech_id,
            event="cancelled",
        )
    await _unescalate_linked_conversation(tenant_id=tenant_id, wo_id=wo_id)
    # CR-0193：生命週期事件（原本 cancel 不落事件流）
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="cancelled",
        payload={"from_status": current, "reason": reason, "technician_id": tech_id},
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.cancelled"
    )


async def _detect_schedule_conflict_and_publish(
    *,
    tenant_id: str,
    wo_id: str,
    technician_id: str,
    window_hours: int = 2,
) -> None:
    """Flow 14 排班衝突偵測 — 同技師 ±window_hours 是否已有其他 active wo。

    偵測到衝突時：
      - INSERT work_order_events `event_type='schedule_conflict'`，
        payload 含 conflicting_wo_ids / technician_id / window_hours
      - WS publish 至 `/realtime/dispatch-queue`（admin 已訂閱）
        type='schedule_conflict_detected'

    不 raise — 衝突偵測為「軟訊號」，admin 可決定是否 reassign / reschedule；
    不阻擋既有 assign 路徑。失敗（DB / WS）也 swallow，避免影響主流。
    """
    if not await _ensure_conn():
        return
    try:
        cur = await db_module._conn.execute(
            "SELECT scheduled_at FROM work_orders WHERE id = %s::uuid",
            (wo_id,),
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return
        scheduled_at = row[0]

        cur = await db_module._conn.execute(
            "SELECT id, scheduled_at FROM work_orders "
            "WHERE tenant_id = %s::uuid "
            "  AND technician_id = %s::uuid "
            "  AND id != %s::uuid "
            "  AND status NOT IN ('completed', 'confirmed', 'cancelled') "
            "  AND scheduled_at IS NOT NULL "
            "  AND scheduled_at BETWEEN "
            "      %s::timestamptz - (INTERVAL '1 hour' * %s) "
            "      AND %s::timestamptz + (INTERVAL '1 hour' * %s)",
            (tenant_id, technician_id, wo_id,
             scheduled_at, window_hours, scheduled_at, window_hours),
        )
        rows = await cur.fetchall()
        if not rows:
            return

        conflicting_ids = [str(r[0]) for r in rows]
        payload = {
            "conflicting_wo_ids": conflicting_ids,
            "technician_id": str(technician_id),
            "window_hours": window_hours,
            "scheduled_at": scheduled_at.isoformat() if hasattr(scheduled_at, "isoformat") else str(scheduled_at),
        }
        await _insert_wo_event(
            wo_id=wo_id, tenant_id=tenant_id, actor_user_id=None,
            event_type="schedule_conflict", payload=payload,
        )
        try:
            from realtime.ws_hub import hub
            await hub.publish(
                "/realtime/dispatch-queue",
                {
                    "type": "schedule_conflict_detected",
                    "payload": {
                        "work_order_id": str(wo_id),
                        **payload,
                    },
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("ws publish schedule_conflict failed (non-fatal)")
        # CR-0017 Stage 1.2 — enqueue LINE Flex push (worker render conflict
        # 通知 admin 或客戶；補救流由業主 admin 決定走 reassign/reschedule)。
        try:
            from services import line_push_outbox_service
            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id,
                push_kind="schedule_conflict",
                payload=payload,
                reference_id=str(wo_id),
                reference_table="work_orders",
            )
        except Exception:  # noqa: BLE001
            logger.exception("outbox enqueue schedule_conflict failed (non-fatal)")
    except Exception:  # noqa: BLE001
        logger.exception("schedule conflict detection failed (non-fatal)")


async def _assert_not_high_risk_hold(wo_id: str) -> None:
    """CR-0041 BR-M15-03：high_risk_hold 旗標為 TRUE → 擋派工/完工（422）。

    工單因 high/critical 異常被暫停；須先 resolve 該異常（exception_service）解除 hold 才能繼續。
    """
    cur = await db_module._conn.execute(
        "SELECT high_risk_hold FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    if row and row[0]:
        raise ApiError(
            "HIGH_RISK_HOLD",
            "工單處於高風險暫停（high_risk_hold）；須先處理對應異常案件才能繼續（BR-M15-03）",
            422,
        )


# CR-0095 D2：派工前報價同意 gate 的 override 角色（沿用 FULL_ACCESS / ops 慣例）
_QUOTE_GATE_OVERRIDE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除


async def _assert_quote_accepted(
    wo_id: str, actor_role: str | None, override_reason: str | None,
) -> None:
    """CR-0095 D2（業主裁決：一律需報價同意）：派工前工單須有 accepted 報價，否則 409。

    過期報價不算 accepted（D4：過期視同未同意）。主管（admin/ops）帶 override_reason
    可強制派工（急修安全閥，沿用 CR-0042 開單 override 模式；稽核由 router 記）。
    """
    if (
        actor_role in _QUOTE_GATE_OVERRIDE_ROLES
        and override_reason
        and override_reason.strip()
    ):
        logger.info("assign quote-gate overridden by %s for wo=%s", actor_role, wo_id[:8])
        return
    cur = await db_module._conn.execute(
        "SELECT COUNT(*) FROM quote "
        "WHERE work_order_id = %s::uuid AND state = 'accepted'",
        (wo_id,),
    )
    n = int((await cur.fetchone())[0])
    if n == 0:
        raise ApiError(
            "QUOTE_NOT_ACCEPTED",
            "派工前須有已同意的報價（客戶須先在 LINE 同意報價）；"
            "主管可帶 override_reason 強制派工",
            409,
        )


async def _assert_brand_authorized(
    wo_id: str, technician_id: str, actor_role: str | None, override_reason: str | None,
) -> None:
    """手動派工品牌授權 fail-closed（UAT 缺口修補）：工單品牌若有授權名單，
    被指派技師須在名單內，否則 403。

    語意對齊 dispatch_service._brand_authorized_ids。

    **2026-07-31 fail-closed 修正（TC-DISPATCH-06）**：原本「該品牌無任何授權資料」
    → 不阻擋，理由是「避免未建授權的品牌全面無法派工」。但那讓閘門在**最需要它的
    情境**（名單還沒建 = 沒人被驗證過）失效，且整合測試計畫明文要求 fail-closed。
    改為一律擋下，錯誤訊息直接指出兩條出路（建名單 / 主管 override），
    不是讓人對著 403 猜。

    主管（admin/ops）帶 override_reason 的安全閥**維持不變** —— 這是 fail-closed
    可以安全落地的前提：品牌授權名單尚未建立時，營運仍有合法途徑把單派出去。
    （沿用報價 gate / 熔斷同一安全閥；稽核由 router 記。）
    """
    if (
        actor_role in _QUOTE_GATE_OVERRIDE_ROLES
        and override_reason
        and override_reason.strip()
    ):
        logger.info("assign brand-auth overridden by %s for wo=%s", actor_role, wo_id[:8])
        return
    brow = await (await db_module._conn.execute(
        "SELECT brand FROM work_orders WHERE id = %s::uuid", (wo_id,))).fetchone()
    brand = brow[0] if brow else None
    if not brand:
        return  # 無品牌資訊無從判斷（_assert_dispatch_ready 另有品牌必填 gate）
    conn = await db_module.require_tech_conn()
    auth = await (await conn.execute(
        "SELECT technician_id FROM technician_brand_authorization "
        "WHERE brand = %s AND authorized = TRUE "
        "  AND (cert_expires_at IS NULL OR cert_expires_at >= CURRENT_DATE)",
        (brand,))).fetchall()
    if not auth:
        # fail-closed：無授權資料 ≠ 可以派給任何人（TC-DISPATCH-06）。
        # 但由 M18 開關控制是否真的擋（CR-0197 D1(c)，預設 off）——
        # 與 dispatch_service._brand_authorized_ids 共用同一個開關，語意必須一致。
        from services.dispatch_service import brand_auth_enforced

        if not await brand_auth_enforced():
            logger.info(
                "品牌「%s」無有效授權技師，但 dispatch_policy.brand_auth_enforce 未啟用 "
                "→ 手動派工不阻擋 wo=%s", brand, wo_id[:8],
            )
            return
        logger.warning(
            "品牌「%s」無任何有效授權技師，手動派工被擋 wo=%s", brand, wo_id[:8]
        )
        raise ApiError(
            "BRAND_AUTHORIZATION_LIST_EMPTY",
            f"品牌「{brand}」尚未建立任何技師授權名單，依授權閘門不可派工。"
            f"請先於平台後台建立該品牌的技師授權，或由主管帶 override_reason 強制派工",
            403,
        )
    authorized_ids = {str(r[0]) for r in auth}
    if technician_id not in authorized_ids:
        raise ApiError(
            "TECHNICIAN_BRAND_NOT_AUTHORIZED",
            f"技師未取得品牌「{brand}」授權，不可派工；主管可帶 override_reason 強制派工",
            403,
        )


async def assign_order(
    *,
    tenant_id: str,
    wo_id: str,
    technician_id: str,
    reason_code: str,
    reason_text: str | None = None,
    actor_role: str | None = None,
    actor_user_id: str | None = None,
    override_reason: str | None = None,
) -> dict:
    """created | assigned → assigned。

    驗證技師同租戶且 status='active'；附加 [ASSIGNED] 註記到 service_report。
    MVP 不執行 circuit-breaker / cross-area / skill-shortage 規則檢查（OpenAPI
    override_flags 接受但忽略），留待派工引擎模組接入後啟用。

    CR-0095 D2：派工前須有客戶已同意的報價（QUOTE_NOT_ACCEPTED 409）；
    主管（actor_role∈admin/ops）帶 override_reason 可強制派工。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _ASSIGN_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot assign work order in status '{current}'; expected one of {sorted(_ASSIGN_FROM)}",
            409,
        )

    # CR-0026 / BR-M05-03：派工前必填欄位 gate（缺品牌/型號/地址/問題類型 → 422）
    await _assert_dispatch_ready(wo_id)
    # CR-0041 / BR-M15-03：high_risk_hold 擋派工
    await _assert_not_high_risk_hold(wo_id)
    # CR-0095 D2：報價同意 gate（一律需 accepted 報價；主管可 override）
    await _assert_quote_accepted(wo_id, actor_role, override_reason)

    # CR-0114 R4：共用師傅庫模式下,候選可見全部 authority 師傅,但 wo FK 指向
    # 品牌庫投影 → 指派前先確保該師傅投影存在（單庫 fallback 為 no-op）。
    from core.tech_mirror import ensure_technician_projection
    await ensure_technician_projection(technician_id)

    # Verify technician exists, same tenant, active
    cur = await db_module._conn.execute(
        "SELECT id, status, online_state FROM technicians "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (technician_id, tenant_id),
    )
    tech_row = await cur.fetchone()
    if not tech_row:
        raise ApiError("TECHNICIAN_NOT_FOUND", "Technician not found in this tenant", 404)
    if tech_row[1] != "active":
        raise ApiError(
            "TECHNICIAN_NOT_AVAILABLE",
            f"Technician status is '{tech_row[1]}'; only 'active' technicians can accept assignments",
            409,
        )
    # CR-0117 S5：熔斷中技師擋派工 —— TECHNICIAN_CIRCUIT_BREAKER_OPEN 錯誤碼與前端
    # dispatch-manual 的 409 處理先前皆為死碼（後端從不 raise，候選過濾又判錯欄位）。
    # 主管帶 override_reason 可強制派工（急修安全閥，沿用報價 gate 同模式）。
    if tech_row[2] == "circuit_breaker_open" and not (
        actor_role in _QUOTE_GATE_OVERRIDE_ROLES
        and override_reason
        and override_reason.strip()
    ):
        raise ApiError(
            "TECHNICIAN_CIRCUIT_BREAKER_OPEN",
            "技師目前熔斷中（circuit_breaker_open），不可派工；主管可帶 override_reason 強制派工",
            409,
        )
    # 品牌授權 fail-closed（UAT 缺口）：手動派工亦須驗品牌授權，主管可 override
    await _assert_brand_authorized(wo_id, technician_id, actor_role, override_reason)

    note = f"[ASSIGNED:{reason_code}]"
    if reason_text:
        note += f" {reason_text}"

    # CR-0030：依租戶派工模式標記 dispatched_via（platform_paid → 'platform' 可計費事件）
    from services import dispatch_mode_service
    _via = dispatch_mode_service.via_for_mode(
        await dispatch_mode_service.get_dispatch_mode(tenant_id)
    )

    # CR-0199：樂觀條件——指派不可覆蓋期間被取消或已被他人指派的單
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  technician_id = %s::uuid, "
        "  status = 'assigned', "
        "  dispatched_via = %s, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (technician_id, _via, note, wo_id, sorted(_ASSIGN_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_ASSIGN_FROM, action="指派")
    # CR-0165 F9：手動派工補 dispatch_logs（原僅 reassign 寫，四條手動入口全斷鏈）。
    # action='assign' 對齊 API enum / seeds 慣例；match_score/factors 留 NULL（人工派無演算法分數）。
    await db_module._conn.execute(
        "INSERT INTO dispatch_logs "
        "  (work_order_id, action, technician_id, notes) "
        "VALUES (%s::uuid, 'assign', %s::uuid, %s)",
        (wo_id, technician_id, note),
    )
    # 也寫一筆 work_order_events 對齊 reassign 的 timeline 觀感
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="assign",
        payload={
            "technician_id": str(technician_id),
            "reason_code": reason_code,
            "reason_text": reason_text,
            "from_status": current,
        },
    )
    # Flow 14 排班衝突軟偵測（best-effort，不阻擋 assign）
    await _detect_schedule_conflict_and_publish(
        tenant_id=tenant_id, wo_id=wo_id, technician_id=technician_id,
    )
    # /realtime/pool/{tech_id} publish — 對齊前端 pool/page.tsx 契約
    # event=added 帶完整 wo 物件 → 前端列表 prepend
    await _publish_pool_change(
        tenant_id=tenant_id, wo_id=wo_id, technician_id=technician_id,
        event="added",
    )
    # CR-0028 斷點 1 — 派工完成推 LINE 給客戶（best-effort，複用 CR-0017 outbox）
    try:
        from services import line_push_outbox_service
        doc_cur = await db_module._conn.execute(
            "SELECT document_number FROM work_orders WHERE id = %s::uuid", (wo_id,)
        )
        doc_row = await doc_cur.fetchone()
        await line_push_outbox_service.enqueue(
            tenant_id=tenant_id,
            push_kind="work_order_assigned",
            payload={
                "work_order_id": wo_id,
                "document_number": doc_row[0] if doc_row else None,
            },
            reference_id=wo_id,
            reference_table="work_orders",
        )
    except Exception:  # noqa: BLE001
        logger.exception("outbox enqueue work_order_assigned failed (non-fatal)")
    # CR-0062：事件驅動通知 — 通知被指派技師（其登入帳號 technicians.user_id）
    try:
        tcur = await db_module._conn.execute(
            "SELECT user_id FROM technicians WHERE id = %s::uuid", (technician_id,))
        trow = await tcur.fetchone()
        if trow and trow[0]:
            await _auto_notify(
                tenant_id, trow[0], "work_order_assigned",
                "新工單已派給你", "請至『我的工單』查看並接單。",
                wo_id=wo_id,
            )
    except Exception:  # noqa: BLE001
        logger.exception("assign auto-notify failed (non-fatal)")
    result = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.assigned"
    )
    # CR-0169/CR-0172:指派 LINE 推播(HD-3 指派必推;fail-soft、內容最小化)。
    # flag 開啟走 outbox 取得送達保證(閉合 R10),否則走舊同步 HTTP。
    await _dispatch_tech_notify(
        tenant_id=tenant_id, wo_id=wo_id, technician_id=technician_id,
        wo_summary=_tech_line_wo_summary(result),
    )
    return result


async def reassign_order(
    *,
    tenant_id: str,
    wo_id: str,
    new_technician_id: str,
    reason: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> dict:
    """Flow 8 二次派工 — admin 強制改派（不破壞 wo_id / events / customer history）。

    與 assign_order 差異：
      - 接受 _REASSIGN_FROM = {assigned, accepted, in_progress}（涵蓋 accepted/
        in_progress，後兩者 assign_order 拒絕）
      - 強制收回後 status 回到 'assigned'（即使原本 accepted/in_progress）
      - 寫 dispatch_logs.action='reassign' 留 audit 軌跡
      - 422 NO_OP_SAME_TECHNICIAN 若新舊技師相同

    使用情境：
      - admin 發現指派錯誤但工單已 accepted
      - 客戶要求換技師
      - 原技師臨時無法執行（病假 / 排程衝突）但 wo 已開始
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # CR-0048 / BR-M05-01：改派必填原因（status_reason gate，與 cancel/escalate 一致）
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "改派工單必須填寫原因（BR-M05-01）", 422)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _REASSIGN_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reassign work order in status '{current}'; "
            f"expected one of {sorted(_REASSIGN_FROM)}",
            409,
        )

    # 取得原技師
    cur = await db_module._conn.execute(
        "SELECT technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    old_technician_id = str(row[0]) if row and row[0] else None
    if old_technician_id == str(new_technician_id):
        raise ApiError(
            "NO_OP_SAME_TECHNICIAN",
            "new_technician_id is the same as current technician",
            422,
        )

    # CR-0114 R4：改派前確保新師傅投影存在（共用師傅庫 → 品牌庫投影;fallback no-op）
    from core.tech_mirror import ensure_technician_projection
    await ensure_technician_projection(new_technician_id)

    # 驗新技師同 tenant + active
    cur = await db_module._conn.execute(
        "SELECT id, status FROM technicians "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (new_technician_id, tenant_id),
    )
    tech_row = await cur.fetchone()
    if not tech_row:
        raise ApiError(
            "TECHNICIAN_NOT_FOUND",
            "new technician not found in this tenant",
            404,
        )
    if tech_row[1] != "active":
        raise ApiError(
            "TECHNICIAN_NOT_AVAILABLE",
            f"new technician status is '{tech_row[1]}'; only 'active' can be reassigned",
            409,
        )
    # 品牌授權 fail-closed（同 assign）：改派亦驗新技師品牌授權。reassign 必填
    # reason，故對主管（admin/ops）等同帶 override_reason 放行；非 override 角色
    # （如 dispatcher）改派未授權技師則擋。
    await _assert_brand_authorized(wo_id, str(new_technician_id), actor_role, reason)

    note = f"[REASSIGN] {old_technician_id or 'unassigned'} → {new_technician_id}: {reason}"
    # CR-0199：樂觀條件——改派不可覆蓋期間被取消或技師已自行接單的單
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  technician_id = %s::uuid, "
        "  status = 'assigned', "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        # CR-0048 / BR-M05-01：改派原因落結構化 status_reason（不只塞 service_report 字串）
        "  status_reason = %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (new_technician_id, note, reason.strip(), wo_id, sorted(_REASSIGN_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_REASSIGN_FROM, action="改派")
    # dispatch_logs audit（schema: 無 tenant_id；隔離靠 join）
    await db_module._conn.execute(
        "INSERT INTO dispatch_logs "
        "  (work_order_id, action, technician_id, notes) "
        "VALUES (%s::uuid, 'reassign', %s::uuid, %s)",
        (wo_id, new_technician_id, reason),
    )
    # 也寫一筆 work_order_events 對齊 subflow timeline 觀感
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="reassign",
        payload={
            "old_technician_id": old_technician_id,
            "new_technician_id": str(new_technician_id),
            "reason": reason,
            "from_status": current,
        },
    )
    result = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.reassigned"
    )
    # CR-0169/CR-0172:改派也推播給新技師(fail-soft;flag 開啟走 outbox)
    await _dispatch_tech_notify(
        tenant_id=tenant_id, wo_id=wo_id, technician_id=new_technician_id,
        wo_summary=_tech_line_wo_summary(result),
    )
    return result


async def escalate_order(
    *,
    tenant_id: str,
    wo_id: str,
    level: str,
    reason: str,
    actor_user_id: str | None = None,  # CR-0193 生命週期事件 actor
) -> dict:
    """升級工單至 operations_manager / tenant_admin。

    DB 沒有專屬升級欄位。本實作：
      - service_report append `[ESCALATED:{level}] {reason}` 留稽核軌跡
      - priority 推進到 'urgent'（若原本不是 urgent）
      - 不改 status — 升級為「上層覆審」流程，原狀態維持
    後續若上層加開 escalation_logs 表，把寫入點接過去即可。
    """
    if level not in _ESCALATE_LEVELS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"level must be one of {sorted(_ESCALATE_LEVELS)}",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _ESCALATE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot escalate work order in status '{current}'; "
            f"expected one of {sorted(_ESCALATE_FROM)}",
            409,
        )

    note = f"[ESCALATED:{level}] {reason.strip()[:500]}"
    # CR-0199：本轉換不切 status，但升級的前提是單仍未結案（_ESCALATE_FROM），
    # 期間被取消/完工就不該再升級——綁允許集合，語意同前置檢查
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  priority = CASE WHEN priority = 'urgent' THEN priority ELSE 'urgent' END, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (note, wo_id, sorted(_ESCALATE_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_ESCALATE_FROM, action="升級")
    # CR-0193：生命週期事件（原本 escalate 不落事件流；本轉換不切 status，
    # 只提 priority，所以事件是唯一能看出「何時被升級、誰升的」的地方）
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="escalated",
        payload={"level": level, "reason": reason, "from_status": current},
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.escalated"
    )


async def _rollup_tech_stats_safe(tenant_id: str, wo_id: str) -> None:
    """CR-0117 S3：完工/評分後回寫 technicians.rating / completed_orders 聚合。

    fail-soft —— 統計回寫是派生資料，任何失敗只 log，絕不阻斷工單主流程。
    """
    try:
        cur = await db_module._conn.execute(
            "SELECT technician_id FROM work_orders WHERE id = %s::uuid",
            (wo_id,),
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return  # 無指派技師 → 無統計可回寫
        from services import technician_service

        await technician_service.rollup_technician_stats(
            tenant_id=tenant_id, technician_id=str(row[0]),
        )
    except Exception:  # noqa: BLE001 — 派生統計失敗不可影響工單流程
        logger.exception("technician stats rollup failed (non-fatal) wo=%s", wo_id)


async def confirm_order(
    *,
    tenant_id: str,
    wo_id: str,
    rating: int,
    feedback: str | None = None,
    actor_user_id: str | None = None,  # CR-0193 生命週期事件 actor
) -> dict:
    """completed → confirmed，寫入客戶評分與意見，set confirmed_at = NOW()。

    rating 1-5 必填，feedback 可留空（最多 1000 字）。終局狀態 — 一旦 confirmed
    不再允許其他寫入動作（與 cancelled 並列為兩個結案形式）。
    """
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        raise ApiError("VALIDATION_ERROR", "rating must be an integer between 1 and 5", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _CONFIRM_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot confirm work order in status '{current}'; expected one of {sorted(_CONFIRM_FROM)}",
            409,
        )

    feedback_clean: str | None = None
    if feedback and feedback.strip():
        feedback_clean = feedback.strip()[:1000]

    # CR-0129 / ADR-015②（D2a 業主裁決）：結案硬閘——報價須客戶確認才可 confirmed；
    # 急件單＝補審完成（佔位報價經 LIFF accept 或紙本 audit_complete 轉 accepted）。
    # 僅驗 gate 後新單（quote_gate_applied），存量豁免（CR-0128 D3a）。
    gcur = await db_module._conn.execute(
        "SELECT quote_gate_applied FROM work_orders WHERE id = %s::uuid", (wo_id,))
    grow = await gcur.fetchone()
    if grow and bool(grow[0]):
        qcur = await db_module._conn.execute(
            "SELECT 1 FROM quote WHERE work_order_id = %s::uuid AND state = 'accepted' LIMIT 1",
            (wo_id,))
        if not await qcur.fetchone():
            raise ApiError(
                "QUOTE_NOT_CONFIRMED_FOR_CLOSE",
                "結案前報價須經客戶確認——急件單請完成事後補審（LIFF 確認或紙本簽認）"
                "（ADR-015②/15_SDS §4.5）",
                422,
            )

    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'confirmed', "
        "  confirmed_at = NOW(), "
        "  rating = %s, "
        "  feedback = COALESCE(%s, feedback), "
        # CR-0043 Tier②：客戶確認結案 → 完工細狀態進「已結案」（M05 Q052 終點）
        "  completion_status = 'closed', "
        "  updated_at = NOW() "
        # CR-0199：樂觀條件——客戶確認不可覆蓋期間被取消的單
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (rating, feedback_clean, wo_id, sorted(_CONFIRM_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_CONFIRM_FROM, action="客戶確認")
    # CR-0117 S3：評分落庫後回寫技師聚合統計（fail-soft）
    await _rollup_tech_stats_safe(tenant_id, wo_id)
    # CR-0193：生命週期事件（原本 confirm 不落事件流 → 結案這個終點在 timeline 上不存在）
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="confirmed",
        payload={"from_status": current, "rating": rating, "has_feedback": bool(feedback_clean)},
    )
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.confirmed"
    )


async def propose_reschedule(
    *,
    tenant_id: str,
    wo_id: str,
    proposed_slots: list[dict],
    message_to_customer: str,
    send_via: str = "line",
    warning_acknowledged_at: str | None = None,
) -> dict:
    """送出改期請求 — 取首選時段為新 scheduled_at，並把 1-3 個備選寫入稽核軌跡。

    MVP 範圍：
      - 不真的呼叫 LINE/SMS push（SOP 由派工通知模組接管）
      - 不建獨立 reschedule_slots 表（24h 內 3 次上限以 service_report 內 [RESCHEDULE] 標記計算）
      - state machine：assigned | accepted | in_progress 才允許改期
      - 首個 slot 的 start 寫入 scheduled_at 作為「假定接受」基準；客戶 RSVP 後再修正

    錯誤：
      - 422 RESCHEDULE_LIMIT_EXCEEDED：24h 內已 3 次
      - 409 STATE_CONFLICT：工單已結案 / 已取消
      - 409 RESCHEDULE_SLOT_TAKEN：首選 slot start 與其他工單衝突（同技師同時段）
    """
    if not proposed_slots or not isinstance(proposed_slots, list):
        raise ApiError("VALIDATION_ERROR", "proposed_slots is required", 422)
    if len(proposed_slots) > 3:
        raise ApiError("VALIDATION_ERROR", "proposed_slots accepts at most 3 items", 422)
    if not message_to_customer or not message_to_customer.strip():
        raise ApiError("VALIDATION_ERROR", "message_to_customer is required", 422)
    if len(message_to_customer) > 120:
        raise ApiError("VALIDATION_ERROR", "message_to_customer must be at most 120 chars", 422)
    if send_via not in {"line", "line_and_sms"}:
        raise ApiError("VALIDATION_ERROR", "send_via must be 'line' or 'line_and_sms'", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reschedule work order in status '{current}'; expected one of {sorted(_RESCHEDULE_FROM)}",
            409,
        )

    # 24h 內改期次數 — 從 service_report 計 [RESCHEDULE] 標記出現次數
    cur = await db_module._conn.execute(
        "SELECT service_report, technician_id FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    report_text = row[0] or "" if row else ""
    technician_id = row[1] if row else None
    # 簡單計數 — service_report 是 append-only，[RESCHEDULE@<iso>] 標記每次寫一筆
    import datetime as _dt
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=24)
    recent_count = 0
    for line in report_text.splitlines():
        if "[RESCHEDULE@" not in line:
            continue
        # 解 [RESCHEDULE@<iso>] 取時間戳
        try:
            iso = line.split("[RESCHEDULE@", 1)[1].split("]", 1)[0]
            ts = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=_dt.timezone.utc)
            if ts >= cutoff:
                recent_count += 1
        except (ValueError, IndexError):
            continue
    if recent_count >= _RESCHEDULE_LIMIT_24H:
        raise ApiError(
            "RESCHEDULE_LIMIT_EXCEEDED",
            f"Reschedule limit exceeded: {recent_count} times in last 24h",
            422,
        )

    # 首選 slot 的 start 作為新 scheduled_at
    first_slot = proposed_slots[0]
    new_start = first_slot.get("start")
    if not new_start:
        raise ApiError("VALIDATION_ERROR", "first proposed slot is missing 'start'", 422)

    # 同技師同時段衝突檢查（best-effort — 同 technician_id 在同 start 時間已有別張未結案工單）
    if technician_id:
        cur = await db_module._conn.execute(
            "SELECT 1 FROM work_orders "
            "WHERE technician_id = %s::uuid "
            "  AND id <> %s::uuid "
            "  AND status NOT IN ('completed','confirmed','cancelled') "
            "  AND scheduled_at = %s::timestamptz "
            "LIMIT 1",
            (str(technician_id), wo_id, new_start),
        )
        if await cur.fetchone():
            raise ApiError(
                "RESCHEDULE_SLOT_TAKEN",
                "First proposed slot conflicts with another work order assigned to the same technician",
                409,
            )

    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
    slots_summary = "; ".join(
        f"{s.get('start','?')}~{s.get('end','?')}" for s in proposed_slots
    )
    note = (
        f"[RESCHEDULE@{now_iso}] via={send_via} slots={slots_summary} "
        f"msg={message_to_customer.strip()[:120]}"
    )
    if warning_acknowledged_at:
        note += f" ack={warning_acknowledged_at}"

    # CR-0199：改期不切 status，但前提是單仍在 _RESCHEDULE_FROM（未結案）
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  scheduled_at = %s::timestamptz, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (new_start, note, wo_id, sorted(_RESCHEDULE_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_RESCHEDULE_FROM, action="改期")
    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.rescheduled"
    )


async def get_dispatch_queue_snapshot(*, tenant_id: str) -> dict:
    """派工佇列快照：pending / assigning / assigned + sla_at_risk。

    OpenAPI 語義 → DB status mapping：
      - pending   = 'created'   工單剛建立、尚未派工
      - assigning = 'assigned'  系統已指派、等技師回應
      - assigned  = 'accepted'  技師已接受（已派工確認）
    in_progress / completed / confirmed / cancelled 均不計入派工佇列。

    sla_at_risk：尚未結案且預定時間落在「現在起 2 小時內」（含已過期），
    用一個 SQL FILTER 子句一次算完，不分窗。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT "
        f"  COUNT(*) FILTER (WHERE wo.status = 'created')  AS pending, "
        f"  COUNT(*) FILTER (WHERE wo.status = 'assigned') AS assigning, "
        f"  COUNT(*) FILTER (WHERE wo.status = 'accepted') AS assigned, "
        f"  COUNT(*) FILTER (WHERE wo.status NOT IN ('completed','confirmed','cancelled') "
        f"                     AND wo.scheduled_at IS NOT NULL "
        f"                     AND wo.scheduled_at < NOW() + INTERVAL '2 hours') AS sla_at_risk "
        f"{_WO_JOIN} "
        f"WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (tenant_id,))
    row = await cur.fetchone()
    return {
        "pending": int(row[0] or 0) if row else 0,
        "assigning": int(row[1] or 0) if row else 0,
        "assigned": int(row[2] or 0) if row else 0,
        "sla_at_risk": int(row[3] or 0) if row else 0,
    }


async def get_today_stats(*, tenant_id: str) -> dict:
    """Dashboard 派工 KPI：今日工單數 + 完工率 + 逾時工單。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    sql = (
        f"SELECT "
        f"  COUNT(*) FILTER (WHERE wo.created_at >= date_trunc('day', NOW())) AS today_count, "
        f"  COUNT(*) FILTER (WHERE wo.created_at >= date_trunc('day', NOW()) "
        f"                     AND wo.status IN ('completed','confirmed')) AS completed_today, "
        f"  COUNT(*) FILTER (WHERE wo.status NOT IN ('completed','confirmed','cancelled') "
        f"                     AND wo.scheduled_at IS NOT NULL "
        f"                     AND wo.scheduled_at < NOW()) AS overdue_count "
        f"{_WO_JOIN} "
        f"WHERE COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (tenant_id,))
    row = await cur.fetchone()
    today_count = int(row[0] or 0) if row else 0
    completed_today = int(row[1] or 0) if row else 0
    overdue_count = int(row[2] or 0) if row else 0
    completion_rate = (completed_today / today_count) if today_count > 0 else None
    return {
        "today_count": today_count,
        "completion_rate": completion_rate,
        "overdue_count": overdue_count,
    }


# =============================================================================
# Subflow events (T5–T8)
# =============================================================================
# 設計：以結構化標籤 prepend 到 service_report 文字欄位，避免新增 schema。
# 各事件帶 [TAG] 前綴 + ISO timestamp + JSON 序列化的細節。後續可遷移至獨立
# work_order_events 表。
#
# 對應前端：
#   /my-orders/[id]/scope-change       → POST /work-orders/{id}/scope-change
#   /my-orders/[id]/material-request   → POST /work-orders/{id}/material-request
#   /my-orders/[id]/delay              → POST /work-orders/{id}/delay
#   /my-orders/[id]/door-check         → POST /work-orders/{id}/door-check

# 子流程允許狀態：技師作業中（含 assigned 之後到 in_progress；不含 completed 後）
_SUBFLOW_FROM = {"assigned", "accepted", "in_progress"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_TAG_TO_EVENT_TYPE = {
    "SCOPE_CHANGE": "scope_change",
    "MATERIAL_REQUEST": "material_request",
    "DELAY": "delay",
    "DOOR_CHECK": "door_check",
}


async def _append_subflow_event(
    *,
    tenant_id: str,
    wo_id: str,
    tag: str,
    payload: dict,
    actor_user_id: str | None = None,
) -> dict:
    """驗 status → INSERT 一筆 work_order_events → bump updated_at → 推 WS → 回傳。

    v1.30.0 重構：從 service_report 文字 append 改為結構化事件表寫入，
    便於後續 timeline / 統計 / 稽核查詢。service_report 不再被 subflow 修改。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot record {tag} in status '{current}'; expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )
    event_type = _TAG_TO_EVENT_TYPE.get(tag, "other")
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type=event_type, payload=payload,
    )
    # 仍 bump updated_at 讓既有 list 排序對齊
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )
    return await _publish_and_return(
        tenant_id=tenant_id,
        wo_id=wo_id,
        event_type=f"work_order.subflow.{event_type}",
    )


# CR-0038 桶4 / BR-M08-02：scope change 金額分級閘預設（門檻入 M18 config 不寫死）
_SCOPE_TIER_DEFAULTS = {
    "minor_max": 500,       # ≤500 視為 minor（可後續做自動核准）
    "standard_max": 2000,   # 501-2000 為 standard
    "major_pct": 0.5,       # 增幅 ≥ 原價 50% → major（需主管核准），無視金額
}


async def _classify_scope_tier(original_price: float, new_price: float | None) -> dict:
    """BR-M08-02：依增幅金額/比例分級 minor/standard/major。門檻讀 M18 config
    scope_change_policy（缺則 fallback _SCOPE_TIER_DEFAULTS）。major → requires_supervisor。"""
    from services import config_m18_service

    policy = dict(_SCOPE_TIER_DEFAULTS)
    cfg = await config_m18_service.read_global_value(namespace="scope_change_policy")
    if isinstance(cfg, dict):
        policy.update(cfg)

    delta = max(0.0, (new_price or 0.0) - (original_price or 0.0))
    pct = (delta / original_price) if original_price and original_price > 0 else (1.0 if delta else 0.0)
    if delta > float(policy["standard_max"]) or pct >= float(policy["major_pct"]):
        tier = "major"
    elif delta > float(policy["minor_max"]):
        tier = "standard"
    else:
        tier = "minor"
    return {
        "tier": tier,
        "delta": round(delta, 2),
        "pct": round(pct, 4),
        "requires_supervisor": tier == "major",
    }


async def record_scope_change(
    *,
    tenant_id: str,
    wo_id: str,
    reason: str,
    items: list[dict],
    total_estimate: str | None = None,
    actor_user_id: str | None = None,
) -> dict:
    """記錄範圍變更申請（T5；Flow 3）。

    2026-06-05 補完 proposal INSERT 鏈路（之前淺取證腦補 90% 過高，deep audit 校正 65% — `scope_changes` 表 schema 存在但
    0 caller、token mint 機制存在但無 caller）：

      1. 從 wo 取 technician_id（_SUBFLOW_FROM 保證非 NULL）+ estimated_price
      2. INSERT scope_changes 表（status='pending'）
      3. mint public_token (purpose='scope_change', ttl_days=7)
      4. 仍寫 work_order_events SCOPE_CHANGE tag（保留 subflow timeline 觀感）
      5. _publish_and_return 推 WS

    回傳 envelope 加入 `scope_change_id` + `public_token`，caller（admin /
    技師 UI / 後續 LINE Flex push 模組）可拿 token 自行決定通知方式。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot record SCOPE_CHANGE in status '{current}'; expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )

    # 取 wo 的 technician_id + estimated_price 作 scope_changes 必填欄位
    cur = await db_module._conn.execute(
        "SELECT technician_id, estimated_price FROM work_orders WHERE id = %s::uuid",
        (wo_id,),
    )
    row = await cur.fetchone()
    if not row or not row[0]:
        # _SUBFLOW_FROM 理應保證 technician_id 非 NULL，但安全防呆
        raise ApiError(
            "VALIDATION_ERROR",
            "work order has no technician_id; cannot record scope change",
            422,
        )
    technician_id = str(row[0])
    original_price = float(row[1]) if row[1] is not None else 0.0
    # 2026-08-02：原本 except 直接吞成 None。那讓「填了但格式無效」與「根本沒填」
    # 變成同一件事——而後者是合法的（不改價），前者則會讓下面的 _classify_scope_tier
    # 拿不到加價金額而誤判成 minor（不需主管核准），客戶端看到的加價也變成 0。
    # 沒填仍是 None（合法）；填了無效值改回 422，讓呼叫端知道自己傳錯。
    if total_estimate is None or total_estimate == "":
        new_price = None
    else:
        try:
            new_price = float(total_estimate)
        except (TypeError, ValueError) as e:
            raise ApiError(
                "VALIDATION_ERROR",
                f"total_estimate 不是有效金額：{total_estimate!r}",
                422,
            ) from e

    # CR-0038 桶4 / BR-M08-02：金額分級（config 驅動）；major 標 requires_supervisor
    tier_info = await _classify_scope_tier(original_price, new_price)

    # INSERT scope_changes 表
    cur = await db_module._conn.execute(
        "INSERT INTO scope_changes "
        "  (work_order_id, technician_id, reason, "
        "   original_scope, new_scope, original_price, new_price, status) "
        "VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s::jsonb, %s, %s, 'pending') "
        "RETURNING id",
        (
            wo_id,
            technician_id,
            reason,
            # original_scope MVP 留簡化標記；future 可從 problem_card 摘要填
            json.dumps({"snapshot": "from_work_order", "estimated_price": original_price}, ensure_ascii=False),
            # CR-0038 桶4：tier 分級存入 new_scope（無 migration；admin override 可讀）
            json.dumps({"items": items, "total_estimate": total_estimate, "tier": tier_info}, ensure_ascii=False),
            original_price,
            new_price,
        ),
    )
    new_row = await cur.fetchone()
    scope_change_id = str(new_row[0])

    # mint public_token（caller 可給 customer LINE Flex / web link）
    # 延遲 import 避 circular 並讓本 service 不強依賴 token 模組
    try:
        from services import public_token
        token = public_token.generate_token(
            scope_change_id,
            purpose="scope_change",
            ttl_days=7,
            tenant_id=tenant_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("public_token mint failed (non-fatal); returning no token")
        token = None

    # 仍寫 work_order_events 保 subflow timeline
    payload = {
        "reason": reason,
        "items": items,
        "total_estimate": total_estimate,
        "scope_change_id": scope_change_id,
        "tier": tier_info,  # CR-0038 桶4：分級閘結果入 timeline
    }
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="scope_change", payload=payload,
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )

    # token mint log（admin 可從 scope_changes table 查詢；token 由 outbox
    # payload 帶給 worker render Flex 用）
    if token:
        logger.info(
            "scope_change_id=%s token minted (ttl_days=7)",
            scope_change_id,
        )

    # CR-0017 Stage 1.2 — enqueue LINE Flex push (worker render scope_change
    # proposal Flex 含 accept/reject 按鈕 + token 連結)。best-effort 不阻擋主流。
    try:
        from services import line_push_outbox_service
        await line_push_outbox_service.enqueue(
            tenant_id=tenant_id,
            push_kind="scope_change_proposal",
            payload={
                "scope_change_id": scope_change_id,
                "work_order_id": wo_id,
                "reason": reason,
                "items": items,
                "total_estimate": total_estimate,
                "public_token": token,
            },
            reference_id=scope_change_id,
            reference_table="scope_changes",
        )
    except Exception:  # noqa: BLE001
        logger.exception("outbox enqueue scope_change_proposal failed (non-fatal)")

    return await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.subflow.scope_change"
    )


async def record_material_request(
    *,
    tenant_id: str,
    wo_id: str,
    items: list[dict],
    urgency: str,
    note: str | None = None,
) -> dict:
    """記錄缺料回報（T6），等待調度員協調補料。"""
    payload = {"items": items, "urgency": urgency, "note": note}
    return await _append_subflow_event(
        tenant_id=tenant_id,
        wo_id=wo_id,
        tag="MATERIAL_REQUEST",
        payload=payload,
    )


async def mark_material_request_supplied(
    *,
    tenant_id: str,
    wo_id: str,
    material_request_event_id: str,
    supplied_by_user_id: str,
    note: str | None = None,
) -> dict:
    """admin 標記某筆 material_request 已補料完成（Flow 4 收尾）。

    寫 event_type='supply_arrived' 事件，payload 含 material_request_event_id
    指回原回報事件（join 關係）；list_pending_material_requests 以此過濾掉
    已收尾的回報。

    驗證：
      - material_request_event_id 必須存在且同 tenant 且 event_type='material_request'
        且屬於該 wo（防 admin 誤標他單）
      - 同 material_request 不可重複 supplied（DUP_SUPPLY 409）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 確認 wo 存在 + tenant 隔離
    await _fetch_status_for_update(wo_id, tenant_id)
    # 驗 material_request_event
    cur = await db_module._conn.execute(
        "SELECT event_type, work_order_id FROM work_order_events "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid",
        (material_request_event_id, tenant_id),
    )
    row = await cur.fetchone()
    if row is None:
        raise ApiError(
            "EVENT_NOT_FOUND",
            "material_request_event_id not found in this tenant",
            404,
        )
    if row[0] != "material_request":
        raise ApiError(
            "INVALID_EVENT_TYPE",
            f"event {material_request_event_id} is '{row[0]}', expected 'material_request'",
            422,
        )
    if str(row[1]) != str(wo_id):
        raise ApiError(
            "EVENT_WO_MISMATCH",
            "material_request event does not belong to this work order",
            422,
        )
    # 防重複 supplied
    cur = await db_module._conn.execute(
        "SELECT 1 FROM work_order_events "
        "WHERE tenant_id = %s::uuid "
        "  AND event_type = 'supply_arrived' "
        "  AND (payload->>'material_request_event_id')::uuid = %s::uuid "
        "LIMIT 1",
        (tenant_id, material_request_event_id),
    )
    if await cur.fetchone() is not None:
        raise ApiError(
            "DUP_SUPPLY",
            "this material_request has already been marked supplied",
            409,
        )
    # INSERT supply_arrived event
    payload = {
        "material_request_event_id": material_request_event_id,
        "note": note,
    }
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=supplied_by_user_id,
        event_type="supply_arrived", payload=payload,
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )
    return await _publish_and_return(
        tenant_id=tenant_id,
        wo_id=wo_id,
        event_type="work_order.subflow.supply_arrived",
    )


async def record_delay(
    *,
    tenant_id: str,
    wo_id: str,
    delay_minutes: int,
    reason: str,
    reason_text: str | None = None,
    notify: str = "customer_only",
) -> dict:
    """記錄延遲通知（T7）。實際 LINE/SMS 推送由通知服務處理（此處僅留紀錄）。"""
    if delay_minutes < 5 or delay_minutes > 300:
        raise ApiError(
            "VALIDATION_ERROR",
            "delay_minutes must be between 5 and 300",
            422,
        )
    payload = {
        "delay_minutes": delay_minutes,
        "reason": reason,
        "reason_text": reason_text,
        "notify": notify,
    }
    return await _append_subflow_event(
        tenant_id=tenant_id, wo_id=wo_id, tag="DELAY", payload=payload
    )


# TI-M08-01：GPS 到場 proof 業務語意 —— 到場座標與服務地址參考點的 Haversine 距離，
# 與容忍半徑比較。參考座標由 caller（地理編碼）提供於 gps.ref_lat/ref_lng；缺則 proof=None。
_ARRIVAL_GPS_TOLERANCE_M_DEFAULT = 200.0


def compute_arrival_gps_proof(
    ref_lat: float | None,
    ref_lng: float | None,
    gps_lat: float | None,
    gps_lng: float | None,
    tolerance_m: float = _ARRIVAL_GPS_TOLERANCE_M_DEFAULT,
) -> dict | None:
    """到場 GPS proof：回 {distance_m, tolerance_m, within_tolerance}；座標缺漏 → None。

    距離以 Haversine（球面近似，地球半徑 6371km）；within_tolerance = 距離 ≤ 容忍半徑。
    """
    if None in (ref_lat, ref_lng, gps_lat, gps_lng):
        return None
    r = 6371000.0  # 地球半徑（公尺）
    p1, p2 = math.radians(ref_lat), math.radians(gps_lat)
    dphi = math.radians(gps_lat - ref_lat)
    dlmb = math.radians(gps_lng - ref_lng)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    dist = r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return {
        "distance_m": round(dist, 1),
        "tolerance_m": tolerance_m,
        "within_tolerance": dist <= tolerance_m,
    }


async def record_arrival(
    *,
    tenant_id: str,
    wo_id: str,
    arrived_at: str | None = None,
    gps: dict | None = None,
    actor_user_id: str | None = None,
) -> dict:
    """CR-0053：技師到場事件 — 寫 work_order_events event_type='arrival' + 補 started_at（到場時點）。

    修兩個 bug：(1) onsite_arrival 原誤用 record_door_check 寫 event_type='door_check'，
    導致 submit_door_check_v2 的「需先有 arrival 事件」前置閘（查 event_type='arrival'）恆 409；
    (2) started_at 原僅 complete_order 補，到場時點不落 → operational_kpi arrival_on_time 失真。
    狀態限 _SUBFLOW_FROM（assigned/accepted/in_progress）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot record ARRIVAL in status '{current}'; expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )
    # 補到場時點（started_at；COALESCE 不覆蓋既有，arrival KPI 用）
    # CR-0199：到場回報的前提是單仍在 _SUBFLOW_FROM，期間被取消就不該再記到場
    #
    # CR-0205 D1(a)：到場同時把 accepted → in_progress。
    # 為什麼要改：`in_progress` 在此之前是**死值**——正常工單走
    # assigned → accepted → completed，`_WO_TRANSITIONS:917` 的 accepted→in_progress
    # 那條邊沒有任何人走。連帶三個可觀測的資料錯誤：
    #   ① 統計桶（:590-604）的「施工中」恆為 0
    #   ② technician_service.py:512-518 的 online 判定把「人在現場施工」的師傅算成可派
    #   ③ requote_service._ALLOWED_WO_STATUS 針對 in_progress 的分支永遠走不到
    # 業主已於 `15_SDS.md:221` 裁決 `on_site ≡ in_progress`，「到場即施工中」是對該裁決
    # 最直接的落地。CASE 寫在同一句 UPDATE 內＝原子，不會有「started_at 寫了但 status 沒轉」。
    #
    # `assigned` 狀態下到場**刻意維持不動**——那代表技師還沒接單就到場，
    # 屬異常流程，要不要補 assigned→in_progress 這條邊是另一個決策（CR-0205 D1 已標另議）。
    # `in_progress` 重複到場則 CASE 落到 ELSE，維持原狀（冪等）。
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET started_at = COALESCE(started_at, NOW()), "
        "  status = CASE WHEN status = 'accepted' THEN 'in_progress' ELSE status END, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (wo_id, sorted(_SUBFLOW_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_SUBFLOW_FROM, action="到場回報")
    # TI-M08-01：若 gps 帶服務地址參考座標（ref_lat/ref_lng）則算到場 proof（距離+容忍判定）。
    g = gps or {}
    gps_proof = compute_arrival_gps_proof(
        g.get("ref_lat"), g.get("ref_lng"), g.get("lat"), g.get("lng")
    )
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="arrival",
        payload={"arrived_at": arrived_at, "gps": g, "gps_proof": gps_proof},
    )
    result = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.arrived"
    )
    if isinstance(result, dict):
        result["gps_proof"] = gps_proof
    return result


async def record_door_check(
    *,
    tenant_id: str,
    wo_id: str,
    checklist: dict,
    photos_before: list[str] | None = None,
    photos_after: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """記錄門面外觀檢核（T8）。photos 為媒體 URL 清單；MVP 僅記錄 placeholder 名稱。"""
    payload = {
        "checklist": checklist,
        "photos_before": photos_before or [],
        "photos_after": photos_after or [],
        "notes": notes,
    }
    return await _append_subflow_event(
        tenant_id=tenant_id,
        wo_id=wo_id,
        tag="DOOR_CHECK",
        payload=payload,
    )


async def submit_door_check_v2(
    *,
    tenant_id: str,
    wo_id: str,
    checklist: dict,
    photos_before: list[str] | None = None,
    photos_after: list[str] | None = None,
    notes: str | None = None,
) -> dict:
    """CR-0007 HD-01=(a)：door-check 強制 arrival 前置。

    流程：
      1. 查 work_order_events WHERE event_type='arrival'，不存在 → 409
      2. 呼叫 record_door_check（沿用既有路徑，HD-05=freeform 不另驗）
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # tenant + work_order 存在性檢查（順帶確認 tenant scope）
    await _fetch_status_for_update(wo_id, tenant_id)

    cur = await db_module._conn.execute(
        "SELECT 1 FROM work_order_events "
        "WHERE work_order_id = %s::uuid "
        "  AND tenant_id = %s::uuid "
        "  AND event_type = 'arrival' "
        "LIMIT 1",
        (wo_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError(
            "STATE_CONFLICT",
            "door-check requires prior arrival event (CR-0007 HD-01)",
            409,
        )

    return await record_door_check(
        tenant_id=tenant_id,
        wo_id=wo_id,
        checklist=checklist,
        photos_before=photos_before,
        photos_after=photos_after,
        notes=notes,
    )


async def propose_reschedule_v2(
    *,
    tenant_id: str,
    wo_id: str,
    proposed_slots: list[dict],
    message_to_customer: str | None,
    send_via: str,
    proposed_by_user_id: str,
    proposed_by_role: str,
) -> dict:
    """CR-0007 多時段改約提案 v2（寫 saas.reschedule_proposal 獨立表 HD-04=a）。

    HD-02=(a) slots 1-3（DB CHECK 兜底，service 層先驗）
    HD-03=(a) sla_deadline DEFAULT NOW + 24h
    """
    if not isinstance(proposed_slots, list) or not (1 <= len(proposed_slots) <= 3):
        raise ApiError(
            "VALIDATION_ERROR",
            "proposed_slots must be a list of 1-3 items (CR-0007 HD-02)",
            422,
        )
    if send_via not in {"line", "sms", "email"}:
        raise ApiError("VALIDATION_ERROR", "send_via must be line|sms|email", 422)
    if proposed_by_role not in {"technician", "operations_manager", "admin"}:
        raise ApiError(
            "VALIDATION_ERROR",
            "proposed_by_role must be technician|operations_manager|admin",
            422,
        )
    if message_to_customer and len(message_to_customer) > 500:
        raise ApiError("VALIDATION_ERROR", "message_to_customer max 500 chars", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 確認工單存在 + tenant scope（藉用既有狀態查詢）
    await _fetch_status_for_update(wo_id, tenant_id)

    cur = await db_module._conn.execute(
        "INSERT INTO saas.reschedule_proposal "
        "  (work_order_id, tenant_id, proposed_slots, message_to_customer, "
        "   send_via, proposed_by_user_id, proposed_by_role) "
        "VALUES (%s::uuid, %s::uuid, %s::jsonb, %s, %s, %s::uuid, %s) "
        "RETURNING id, status, sla_deadline, created_at",
        (
            wo_id,
            tenant_id,
            json.dumps(proposed_slots, ensure_ascii=False),
            message_to_customer,
            send_via,
            proposed_by_user_id,
            proposed_by_role,
        ),
    )
    row = await cur.fetchone()
    proposal_id = str(row[0])

    # CR-0017 Stage 1.2 — enqueue LINE Flex push (worker 將 render reschedule
    # carousel + push 客戶 LINE)。best-effort 不阻擋主流；send_via='line' 才推。
    if send_via == "line":
        try:
            from services import line_push_outbox_service
            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id,
                push_kind="reschedule_proposal",
                payload={
                    "proposal_id": proposal_id,
                    "work_order_id": wo_id,
                    "proposed_slots": proposed_slots,
                    "message_to_customer": message_to_customer,
                },
                reference_id=proposal_id,
                reference_table="saas.reschedule_proposal",
            )
        except Exception:  # noqa: BLE001
            logger.exception("outbox enqueue reschedule_proposal failed (non-fatal)")

    return {
        "id": proposal_id,
        "work_order_id": wo_id,
        "status": row[1],
        "sla_deadline": row[2].isoformat() if row[2] else None,
        "created_at": row[3].isoformat() if row[3] else None,
        "proposed_slots": proposed_slots,
        "send_via": send_via,
    }


async def list_work_order_events(
    *,
    tenant_id: str,
    wo_id: str,
    event_type: str | None = None,
    limit: int = 100,
) -> dict:
    """列出某工單的事件（依時間倒序）。可依 event_type 過濾。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 先確認工單存在 + tenant 隔離
    await _fetch_status_for_update(wo_id, tenant_id)
    where = ["work_order_id = %s::uuid", "tenant_id = %s::uuid"]
    params: list = [wo_id, tenant_id]
    if event_type:
        where.append("event_type = %s")
        params.append(event_type)
    params.append(limit)
    # CR-0193：改依 seq 排序而非 created_at。seq 是 per-工單連號，回傳它才讓
    # 「事件溯源」在 API 表面驗得到（缺號＝有事件遺失）。
    # ⚠️ 本查詢引用 seq 欄 → migration 122 必須先套用，否則整條讀取 500。
    sql = (
        "SELECT id, event_type, payload, actor_user_id, created_at, seq "
        "FROM work_order_events "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY seq DESC LIMIT %s"
    )
    cur = await db_module._conn.execute(sql, tuple(params))
    rows = await cur.fetchall()
    items = [
        {
            "id": str(r[0]),
            "event_type": r[1],
            "payload": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {}),
            "actor_user_id": str(r[3]) if r[3] else None,
            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            "seq": r[5],
        }
        for r in rows
    ]
    return {"items": items}


async def list_pending_material_requests(
    *,
    tenant_id: str,
    limit: int = 100,
) -> dict:
    """跨工單列出近期的缺料回報（Flow 4 admin 補料管理彙整視圖）。

    每 row 為一筆 material_request 事件 + 對應工單上下文：
      - event_id / created_at / payload (items[], urgency, note)
      - work_order_id / wo_status / scheduled_at / technician_id

    排序：urgency 急迫度（now > today > tomorrow）→ created_at DESC。
    MVP 不分 pending vs supplied（後者需新 event_type 'supply_arrived'
    機制，本 commit OOSCope）；本 endpoint 提供「最近活躍的缺料事件」清單，
    admin 進入工單詳情頁進一步處理。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    if limit < 1 or limit > 500:
        raise ApiError("VALIDATION_ERROR", "limit must be 1..500", 422)

    # LEFT JOIN supply_arrived events 過濾掉已收尾的 material_request（後者
    # 透過 payload->>'material_request_event_id' 指回原 material_request.id）。
    sql = (
        "SELECT "
        "  e.id, e.created_at, e.payload, e.actor_user_id, "
        "  e.work_order_id, wo.status, wo.scheduled_at, wo.technician_id "
        "FROM work_order_events e "
        "JOIN work_orders wo ON e.work_order_id = wo.id "
        "LEFT JOIN work_order_events sa "
        "  ON sa.tenant_id = e.tenant_id "
        "  AND sa.event_type = 'supply_arrived' "
        "  AND (sa.payload->>'material_request_event_id')::uuid = e.id "
        "WHERE e.tenant_id = %s::uuid "
        "  AND e.event_type = 'material_request' "
        "  AND wo.status NOT IN ('completed', 'confirmed', 'cancelled') "
        "  AND sa.id IS NULL "
        "ORDER BY "
        # urgency 優先：now=0 / today=1 / tomorrow=2 / 其他=9
        "  CASE COALESCE(e.payload->>'urgency', '') "
        "    WHEN 'now' THEN 0 "
        "    WHEN 'today' THEN 1 "
        "    WHEN 'tomorrow' THEN 2 "
        "    ELSE 9 END, "
        "  e.created_at DESC "
        "LIMIT %s"
    )
    cur = await db_module._conn.execute(sql, (tenant_id, limit))
    rows = await cur.fetchall()

    items = [
        {
            "event_id": str(r[0]),
            "created_at": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
            "payload": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {}),
            "actor_user_id": str(r[3]) if r[3] else None,
            "work_order_id": str(r[4]),
            "wo_status": r[5],
            "scheduled_at": r[6].isoformat() if hasattr(r[6], "isoformat") else None,
            "technician_id": str(r[7]) if r[7] else None,
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


async def confirm_reschedule_by_customer(
    *,
    tenant_id: str,
    wo_id: str,
    selected_start: str,
    selected_end: str,
) -> dict:
    """客戶於 LINE Flex 選定改期時段 → 寫入 wo.scheduled_at + 紀錄事件 + 推 WS。

    對齊 Flow 11（v1.7.0 frontend 已監聽 reschedule_confirmed_by_customer 事件）。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    try:
        start_dt = datetime.fromisoformat(selected_start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(selected_end.replace("Z", "+00:00"))
    except ValueError as e:
        raise ApiError(
            "VALIDATION_ERROR",
            "selected_start / selected_end 必須為 ISO 8601 格式",
            422,
        ) from e
    if end_dt <= start_dt:
        raise ApiError(
            "VALIDATION_ERROR",
            "selected_end must be after selected_start",
            422,
        )

    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot confirm reschedule in status '{current}'",
            409,
        )

    note = (
        f"[CUSTOMER_RESCHEDULE_CONFIRMED {_now_iso()}] "
        f"customer chose {start_dt.isoformat()}~{end_dt.isoformat()}"
    )
    # CR-0199：客戶確認改期不切 status，前提是單仍在 _RESCHEDULE_FROM
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  scheduled_at = %s::timestamptz, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (start_dt, note, wo_id, sorted(_RESCHEDULE_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_RESCHEDULE_FROM, action="客戶確認改期")
    # 同時寫入結構化事件（v1.30.0 work_order_events）
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id,
        event_type="reschedule_proposed",
        payload={
            "confirmed_by": "customer",
            "selected_start": start_dt.isoformat(),
            "selected_end": end_dt.isoformat(),
        },
    )

    # 推 WS — 前端 v1.13.0 監聽 reschedule_confirmed_by_customer
    try:
        from realtime.ws_hub import hub

        await hub.publish(
            f"/realtime/work-orders/{wo_id}",
            {
                "type": "reschedule_confirmed_by_customer",
                "payload": {
                    "event": "reschedule_confirmed_by_customer",
                    "work_order_id": wo_id,
                    "selected_start": start_dt.isoformat(),
                    "selected_end": end_dt.isoformat(),
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish reschedule_confirmed failed (non-fatal)")

    return await get_order(tenant_id=tenant_id, wo_id=wo_id)


async def reject_reschedule_by_customer(
    *, tenant_id: str, wo_id: str
) -> dict:
    """客戶 LINE Flex 點「都不方便」→ 推 WS 給技師端，wo 狀態不變。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    # 寫事件留下記錄
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id,
        event_type="reschedule_proposed",
        payload={"rejected_by": "customer"},
    )
    try:
        from realtime.ws_hub import hub

        await hub.publish(
            f"/realtime/work-orders/{wo_id}",
            {
                "type": "reschedule_rejected_by_customer",
                "payload": {
                    "event": "reschedule_rejected_by_customer",
                    "work_order_id": wo_id,
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("ws publish reschedule_rejected failed (non-fatal)")

    return await get_order(tenant_id=tenant_id, wo_id=wo_id)


# =============================================================================
# Public anonymous endpoint helper — Q3=C
# =============================================================================
#
# 不帶 tenant gate；呼叫者必須先用 token 解出 work_order_id 才能進來。
# 完工 90 天封存：completed_at < NOW() - 90d 時 raise 410。
# 回傳僅供 PII 遮罩後的展示欄位，不含金額 / 客戶完整地址。


# customer-facing 狀態映射：把內部狀態收斂成消費者能理解的 6 種
_PUBLIC_STATUS_MAP = {
    "created": "pending",
    "assigned": "scheduled",
    "accepted": "scheduled",
    "on_the_way": "on_the_way",
    "in_progress": "in_progress",
    "completed": "completed",
    "confirmed": "completed",
    "cancelled": "cancelled",
}


# =============================================================================
# F-010 Reschedule / Delay quick-action ops（含 LINE Push 真實串接）
# =============================================================================
#
# 與既有的 propose_reschedule (Flow 11 LINE Flex RSVP) / record_delay (T7 事件)
# 互補：
#   - request_reschedule  ：技師 / admin 直接改 scheduled_at，不走 RSVP（單方變更）
#   - approve_reschedule  ：admin 對 request_reschedule 提案做核准 / 退回
#   - notify_delay        ：在 record_delay 之後，主動 LINE push 通知客戶
#
# 三個動作完成後一律寫 audit_event + 嘗試 LINE push（fail-soft）。
#
# Reschedule request lifecycle（state in service_report tag）：
#   [RESCHEDULE_REQUEST@<iso> by=<uid> from=<old_iso> to=<new_iso> reason=<text>]
#   [RESCHEDULE_DECISION@<iso> by=<uid> decision=approve|reject comment=<text>]


_RESCHEDULE_REASON_MAX = 500


async def _audit_action(
    *,
    action: str,
    actor_id: str | None,
    actor_role: str | None,
    work_order_id: str,
    payload: dict,
) -> None:
    """Best-effort audit write — must not fail caller."""
    try:
        from services import audit_log_service

        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            target_type="work_order",
            target_id=work_order_id,
            payload=payload,
        )
    except Exception:  # noqa: BLE001
        logger.warning("audit %s failed", action, exc_info=True)


async def request_reschedule(
    *,
    tenant_id: str,
    wo_id: str,
    new_scheduled_at: str,
    reason: str,
    actor_user_id: str,
    actor_role: str,
) -> dict:
    """Technician / admin requests an immediate reschedule.

    - 技師只能改自己的工單；admin 不限。
    - 不寫 RSVP，直接更新 scheduled_at 並 LINE push 通知客戶（fail-soft）。
    - 回傳：{"work_order": ..., "notification_sent": bool, "channel": "line"|"none",
              "new_scheduled_at": iso}
    """
    # ─── validation ───────────────────────────────────────────────────────
    if not new_scheduled_at:
        raise ApiError("VALIDATION_ERROR", "new_scheduled_at is required", 422)
    try:
        from datetime import datetime as _dt2, timezone as _tz

        new_dt = _dt2.fromisoformat(new_scheduled_at.replace("Z", "+00:00"))
        if new_dt.tzinfo is None:
            new_dt = new_dt.replace(tzinfo=_tz.utc)
    except ValueError as e:
        raise ApiError("VALIDATION_ERROR", "new_scheduled_at must be ISO 8601", 422) from e
    if new_dt <= _dt2.now(_tz.utc):
        raise ApiError(
            "VALIDATION_ERROR",
            "new_scheduled_at must be in the future",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)
    if len(reason) > _RESCHEDULE_REASON_MAX:
        raise ApiError(
            "VALIDATION_ERROR",
            f"reason must be at most {_RESCHEDULE_REASON_MAX} chars",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # ─── tenant + ownership check ─────────────────────────────────────────
    cur = await db_module._conn.execute(
        f"SELECT wo.status, wo.technician_id, wo.scheduled_at {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    current_status, tech_id, old_scheduled = row[0], row[1], row[2]

    if current_status not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot reschedule in status '{current_status}'; "
            f"expected one of {sorted(_RESCHEDULE_FROM)}",
            409,
        )

    # 技師 RBAC：只能改自己被指派的工單
    if actor_role == "technician":
        if tech_id is None or str(tech_id) != actor_user_id:
            raise ApiError(
                "FORBIDDEN",
                "Technicians can only reschedule their own work orders",
                403,
            )

    # ─── apply ────────────────────────────────────────────────────────────
    from datetime import datetime as _dt2, timezone as _tz

    now_iso = _dt2.now(_tz.utc).isoformat()
    note = (
        f"[RESCHEDULE_REQUEST@{now_iso}] by={actor_user_id} "
        f"from={old_scheduled.isoformat() if old_scheduled else 'unset'} "
        f"to={new_dt.isoformat()} reason={reason.strip()[:_RESCHEDULE_REASON_MAX]}"
    )
    # CR-0199：改期申請不切 status，前提是單仍在 _RESCHEDULE_FROM。
    # rowcount 檢查必須擋在下面的 audit 與 LINE push 之前，否則會為一筆沒生效的
    # 改期發出稽核紀錄與客戶通知。
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  scheduled_at = %s::timestamptz, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        # CR-0048 / BR-M05-01：改期原因落結構化 status_reason
        "  status_reason = %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (new_dt, note, reason.strip()[:_RESCHEDULE_REASON_MAX], wo_id,
         sorted(_RESCHEDULE_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_RESCHEDULE_FROM, action="申請改期")

    # ─── audit + LINE push ────────────────────────────────────────────────
    await _audit_action(
        action="work_order.reschedule_requested",
        actor_id=actor_user_id,
        actor_role=actor_role,
        work_order_id=wo_id,
        payload={
            "new_scheduled_at": new_dt.isoformat(),
            "old_scheduled_at": old_scheduled.isoformat() if old_scheduled else None,
            "reason": reason.strip()[:_RESCHEDULE_REASON_MAX],
        },
    )

    from services import line_push_service

    text = (
        f"您的工單 #{wo_id[:8]} 已改約至 "
        f"{new_dt.strftime('%Y-%m-%d %H:%M')}（原因：{reason.strip()[:50]}）"
    )
    notification_sent, channel = await line_push_service.push_to_work_order_customer(
        tenant_id=tenant_id,
        work_order_id=wo_id,
        text=text,
        actor_user_id=actor_user_id,
    )

    order = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.reschedule_requested"
    )
    return {
        "work_order": order,
        "rescheduled": True,
        "new_scheduled_at": new_dt.isoformat(),
        "notification_sent": notification_sent,
        "channel": channel,
    }


async def approve_reschedule(
    *,
    tenant_id: str,
    wo_id: str,
    decision: str,
    comment: str | None,
    actor_user_id: str,
    actor_role: str,
) -> dict:
    """Admin / operations_manager approves or rejects a reschedule request.

    decision='approve' → 不修改 scheduled_at（已在 request 時更新），僅蓋審核章
    decision='reject' → 復原 scheduled_at 至最近一次 [RESCHEDULE_REQUEST] 之 `from`
    """
    if decision not in {"approve", "reject"}:
        raise ApiError("VALIDATION_ERROR", "decision must be 'approve' or 'reject'", 422)
    if comment and len(comment) > _RESCHEDULE_REASON_MAX:
        raise ApiError(
            "VALIDATION_ERROR",
            f"comment must be at most {_RESCHEDULE_REASON_MAX} chars",
            422,
        )

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        f"SELECT wo.status, wo.service_report, wo.scheduled_at {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    current_status, report_text = row[0], (row[1] or "")

    if current_status not in _RESCHEDULE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot approve/reject reschedule in status '{current_status}'",
            409,
        )

    from datetime import datetime as _dt2, timezone as _tz

    now_iso = _dt2.now(_tz.utc).isoformat()

    # 'reject' → 嘗試從最近一筆 [RESCHEDULE_REQUEST] 還原 from
    revert_to: _dt2 | None = None
    if decision == "reject":
        for line in reversed(report_text.splitlines()):
            if "[RESCHEDULE_REQUEST@" not in line or "from=" not in line:
                continue
            # parse "from=<iso>" segment
            try:
                from_seg = line.split("from=", 1)[1].split(" ", 1)[0]
                if from_seg == "unset":
                    break
                revert_to = _dt2.fromisoformat(from_seg.replace("Z", "+00:00"))
                if revert_to.tzinfo is None:
                    revert_to = revert_to.replace(tzinfo=_tz.utc)
                break
            except (ValueError, IndexError):
                continue

    note = (
        f"[RESCHEDULE_DECISION@{now_iso}] by={actor_user_id} "
        f"decision={decision}"
    )
    if comment:
        note += f" comment={comment.strip()[:_RESCHEDULE_REASON_MAX]}"

    if decision == "reject" and revert_to is not None:
        # CR-0199：駁回改期會回寫 scheduled_at，前提是單仍在 _RESCHEDULE_FROM
        # （下面的 else 分支只 append service_report 文字，不綁條件——見 CR-0199 §6
        #  的 SKIP 判定：純文字附加誤擋的代價高於漏擋）
        _cur = await db_module._conn.execute(
            "UPDATE work_orders SET "
            "  scheduled_at = %s::timestamptz, "
            "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
            "  updated_at = NOW() "
            "WHERE id = %s::uuid AND status = ANY(%s)",
            (revert_to, note, wo_id, sorted(_RESCHEDULE_FROM)),
        )
        _assert_transition_applied(_cur, allowed=_RESCHEDULE_FROM, action="駁回改期")
    else:
        await db_module._conn.execute(
            "UPDATE work_orders SET "
            "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
            "  updated_at = NOW() "
            "WHERE id = %s::uuid",
            (note, wo_id),
        )

    await _audit_action(
        action=f"work_order.reschedule_{decision}d",
        actor_id=actor_user_id,
        actor_role=actor_role,
        work_order_id=wo_id,
        payload={
            "decision": decision,
            "comment": (comment or "").strip()[:_RESCHEDULE_REASON_MAX] or None,
            "reverted_to": revert_to.isoformat() if revert_to else None,
        },
    )

    order = await _publish_and_return(
        tenant_id=tenant_id,
        wo_id=wo_id,
        event_type=f"work_order.reschedule_{decision}d",
    )
    return {
        "work_order": order,
        "decision": decision,
        "reverted": revert_to is not None,
    }


async def notify_delay(
    *,
    tenant_id: str,
    wo_id: str,
    delay_minutes: int,
    reason: str,
    actor_user_id: str,
    actor_role: str,
) -> dict:
    """Technician notifies customer of an in-flight delay (LINE push)。

    記錄事件（同 record_delay）+ LINE push（Q8=A V1.0 only LINE）。
    """
    if not isinstance(delay_minutes, int) or delay_minutes < 5 or delay_minutes > 300:
        raise ApiError(
            "VALIDATION_ERROR",
            "delay_minutes must be an integer between 5 and 300",
            422,
        )
    if not reason or not reason.strip():
        raise ApiError("VALIDATION_ERROR", "reason is required", 422)
    if len(reason) > 500:
        raise ApiError("VALIDATION_ERROR", "reason must be at most 500 chars", 422)

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # tenant + ownership check
    cur = await db_module._conn.execute(
        f"SELECT wo.status, wo.technician_id {_WO_JOIN} "
        f"WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (wo_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    current_status, tech_id = row[0], row[1]
    if current_status not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot notify delay in status '{current_status}'; "
            f"expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )
    if actor_role == "technician":
        if tech_id is None or str(tech_id) != actor_user_id:
            raise ApiError(
                "FORBIDDEN",
                "Technicians can only notify delays for their own work orders",
                403,
            )

    # 寫結構化事件（重用 _append_subflow_event 但避免重複狀態檢查 — 直接 INSERT）
    payload = {
        "delay_minutes": delay_minutes,
        "reason": reason.strip()[:500],
        "channel_attempt": "line",
    }
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="delay", payload=payload,
    )
    await db_module._conn.execute(
        "UPDATE work_orders SET updated_at = NOW() WHERE id = %s::uuid",
        (wo_id,),
    )

    await _audit_action(
        action="work_order.delay_notified",
        actor_id=actor_user_id,
        actor_role=actor_role,
        work_order_id=wo_id,
        payload=payload,
    )

    from services import line_push_service

    text = (
        f"您的工單 #{wo_id[:8]} 將延遲約 {delay_minutes} 分鐘抵達，"
        f"造成不便敬請見諒（原因：{reason.strip()[:50]}）"
    )
    notification_sent, channel = await line_push_service.push_to_work_order_customer(
        tenant_id=tenant_id,
        work_order_id=wo_id,
        text=text,
        actor_user_id=actor_user_id,
    )

    order = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.delay_notified"
    )
    return {
        "work_order": order,
        "notification_sent": notification_sent,
        "channel": channel,
    }


async def get_public_status(*, work_order_id: str) -> dict | None:
    """讀取工單對外可揭露的狀態欄位。

    回傳 dict（含未遮罩的技師欄位，由 router 套 mask）；查無資料回 None；
    超過 90 天封存則 raise ApiError(410)。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # UAT-0718 W2-4：補 updated_at 與最新事件時間——「最後更新」須為**真實**
    # 更新時間（completed_at → 最新事件 → updated_at），絕不可拿未來的
    # scheduled_at 充數（原 track 頁「最後更新」顯示未來的預約時間誤導客戶）。
    sql = (
        "SELECT wo.id, wo.status, wo.scheduled_at, wo.completed_at, "
        "       t.name, t.phone, wo.updated_at, "
        "       (SELECT MAX(e.created_at) FROM work_order_events e "
        "        WHERE e.work_order_id = wo.id) AS last_event_at "
        "FROM work_orders wo "
        "LEFT JOIN technicians t ON wo.technician_id = t.id "
        "WHERE wo.id = %s::uuid"
    )
    cur = await db_module._conn.execute(sql, (work_order_id,))
    row = await cur.fetchone()
    if not row:
        return None

    completed_at = row[3]
    if completed_at is not None:
        from datetime import datetime, timedelta, timezone

        archive_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        if completed_at < archive_cutoff:
            raise ApiError("GONE", "工單完工超過 90 天，連結已封存", 410)

    return {
        "work_order_id": str(row[0]),
        "raw_status": row[1],
        "public_status": _PUBLIC_STATUS_MAP.get(row[1], "pending"),
        "scheduled_at": row[2].isoformat() if row[2] else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "technician_name": row[4],
        "technician_phone": row[5],
        "updated_at": row[6].isoformat() if row[6] else None,
        "last_event_at": row[7].isoformat() if row[7] else None,
    }


# ============================================================
# CR-0017 Stage 4 — postback-driven 改約決議 wrapper
# ============================================================

async def confirm_reschedule_by_proposal(
    *, proposal_id: str, slot_idx: int
) -> dict:
    """LINE postback 觸發：依 proposal_id + slot_idx 反查 → confirm reschedule。

    1. SELECT proposed_slots, work_order_id, tenant_id, status FROM saas.reschedule_proposal
    2. 驗 status='pending' + slot_idx 在範圍內
    3. 呼 confirm_reschedule_by_customer 寫 work_orders
    4. UPDATE saas.reschedule_proposal SET chosen_slot_index, customer_responded_at,
       status='customer_confirmed'

    Raises:
        ApiError(404): proposal 不存在
        ApiError(409): proposal 已決議
        ApiError(422): slot_idx 越界
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT work_order_id, tenant_id, proposed_slots, status "
        "FROM saas.reschedule_proposal WHERE id = %s::uuid",
        (proposal_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "reschedule proposal not found", 404)
    wo_id = str(row[0])
    tenant_id = str(row[1])
    proposed_slots = row[2] if isinstance(row[2], list) else json.loads(row[2] or "[]")
    current_status = row[3]
    if current_status != "pending":
        raise ApiError(
            "CONFLICT", f"proposal already decided: {current_status}", 409,
        )
    if slot_idx < 0 or slot_idx >= len(proposed_slots):
        raise ApiError("VALIDATION_ERROR", "slot_idx out of range", 422)

    slot = proposed_slots[slot_idx]
    selected_start = slot.get("start")
    selected_end = slot.get("end") or selected_start
    if not selected_start:
        raise ApiError("VALIDATION_ERROR", "proposed slot missing 'start'", 422)

    # 1. 寫 work_orders（既有 service）
    result = await confirm_reschedule_by_customer(
        tenant_id=tenant_id,
        wo_id=wo_id,
        selected_start=selected_start,
        selected_end=selected_end,
    )

    # 2. CAS update saas.reschedule_proposal
    upd = await db_module._conn.execute(
        "UPDATE saas.reschedule_proposal SET "
        "  status = 'customer_confirmed', "
        "  chosen_slot_index = %s, "
        "  customer_responded_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending' "
        "RETURNING id",
        (slot_idx, proposal_id),
    )
    if not await upd.fetchone():
        # race 不阻斷主流程（work_orders 已寫）
        logger.warning(
            "reschedule_proposal CAS race: id=%s already decided after wo update",
            proposal_id,
        )
    return result


async def reject_reschedule_by_proposal(*, proposal_id: str) -> dict:
    """LINE postback「都不方便」→ reject reschedule + 寫 reschedule_proposal。"""
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT work_order_id, tenant_id, status "
        "FROM saas.reschedule_proposal WHERE id = %s::uuid",
        (proposal_id,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "reschedule proposal not found", 404)
    wo_id = str(row[0])
    tenant_id = str(row[1])
    if row[2] != "pending":
        raise ApiError("CONFLICT", f"proposal already decided: {row[2]}", 409)

    result = await reject_reschedule_by_customer(tenant_id=tenant_id, wo_id=wo_id)
    await db_module._conn.execute(
        "UPDATE saas.reschedule_proposal SET "
        "  status = 'customer_rejected', "
        "  customer_responded_at = NOW(), "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'pending'",
        (proposal_id,),
    )
    return result


# CR-0038 桶4 / Q063：客戶未回 N 小時自動結案（cron 呼叫）
_AUTO_CONFIRM_DEFAULTS = {"enabled": True, "hours": 48}


async def auto_confirm_stale_completed() -> int:
    """Q063：completed 超過 N 小時（config auto_confirm_policy.hours，預設 48）客戶未確認
    → 自動 confirmed/closed。排除 high_risk_hold 與有 open exception_case 的單（客訴/爭議/保固）。
    回傳自動結案筆數。cron 全租戶掃。"""
    if not await _ensure_conn():
        return 0
    from services import config_m18_service

    policy = dict(_AUTO_CONFIRM_DEFAULTS)
    cfg = await config_m18_service.read_global_value(namespace="auto_confirm_policy")
    if isinstance(cfg, dict):
        policy.update(cfg)
    if not policy.get("enabled", True):
        return 0
    hours = int(policy.get("hours", 48))

    cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'confirmed', confirmed_at = NOW(), "
        "  completion_status = 'closed', updated_at = NOW() "
        "WHERE status = 'completed' "
        "  AND completed_at < NOW() - make_interval(hours => %s) "
        "  AND COALESCE(high_risk_hold, FALSE) = FALSE "
        "  AND NOT EXISTS ("
        "    SELECT 1 FROM saas.exception_case ec "
        "    WHERE ec.work_order_id = work_orders.id "
        "      AND ec.status IN ('open', 'investigating', 'escalated')"
        "  ) "
        "RETURNING id, tenant_id",
        (hours,),
    )
    rows = await cur.fetchall()
    # CR-0193：自動結案也要落事件。漏掉的話「被系統自動結案」的單在 timeline 上
    # 完全沒有結案痕跡（比人工結案更需要留痕——沒有人可以問）。
    # actor_user_id=None 代表 system；payload 記 policy 讓事後能重建判斷依據。
    for _id, _tid in (rows or []):
        if not _tid:
            logger.warning("auto_confirm 工單 %s 無 tenant_id，事件略過", _id)
            continue
        try:
            await _insert_wo_event(
                wo_id=str(_id), tenant_id=str(_tid), actor_user_id=None,
                event_type="confirmed",
                payload={"origin": "auto_confirm_stale_completed",
                         "from_status": "completed",
                         "policy_hours": hours},
            )
        except Exception:  # noqa: BLE001 — cron 不因單筆事件失敗而中斷整批
            logger.exception("auto_confirm 事件寫入失敗 wo=%s（非致命）", _id)
    return len(rows or [])
