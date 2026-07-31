"""Dispatch candidates — listDispatchCandidates。

operationId 對齊 openapi.yaml：listDispatchCandidates

設計：
  - 依工單 brand / district 對候選技師排序
  - 綜合分（0~100，audit FR-API-05 五因子）
      = 0.35×skill + 0.25×distance + 0.20×rating + 0.10×load + 0.10×fairness
      skill_match     ∈ [0,1]：brand 命中 +1.0；無 brand 資訊 fallback 0.5
      distance_factor ∈ [0,1]：district 命中 1.0；服務區域命中該縣市 0.6；無交集 0.2
      rating_factor   ∈ [0,1]：rating / 5
      load_factor     ∈ [0,1]：當前在辦工單越少越高（_enrich_workload_fairness 補）
      fairness_factor ∈ [0,1]：近 7 日承接越少越高（雨露均霑；同上補）
    （load/fairness 需 DB，於 skill/distance/rating 基礎分後由 enrichment 疊加）
  - distance_km 為示意值（依 district / 服務區交集回 0 / 5 / 15 / 30）
      待 GIS 模組接入後改為 ST_Distance 真實計算
  - availability_eta_minutes：available=15, busy=60, 其他 None
  - exclude_circuit (default true)：本 phase technicians 表無 circuit_breaker_until 欄
      故只能用 status='inactive' / 'on_leave' 過濾，不會誤剔
  - filters：skills（任一命中）、areas（任一命中）、levels（DB 暫無 level → 不過濾）、rating_min
  - auto_dispatch_attempts：暫回 [] — 待 dispatch_logs 表完整接入
"""

from __future__ import annotations

import logging
from typing import Iterable

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError
from services.technician_service import _TECH_SELECT, _tech_row_to_dict

logger = logging.getLogger("api.dispatch_service")


# audit FR-API-05：派工評分五因子（技能/距離/評分/負載/公平），權重和=1.0。
# load/fairness 於 _enrich_workload_fairness 疊加（需 DB）；基礎分只算前三者。
_W_SKILL = 0.35
_W_DISTANCE = 0.25
_W_RATING = 0.20
_W_LOAD = 0.10       # 當前在辦工單越少越高（避免塞給忙碌技師）
_W_FAIRNESS = 0.10   # 近 7 日承接越少越高（雨露均霑，工作機會分散）
_LOAD_SATURATION = 5  # 在辦 ≥5 張視為滿載（load factor → 0）


def _intersect_lower(a: Iterable[str], b: Iterable[str]) -> bool:
    """case-insensitive 交集判斷，避免 brand/area 大小寫差異漏配。"""
    sa = {str(x).strip().lower() for x in a if x}
    sb = {str(x).strip().lower() for x in b if x}
    return bool(sa & sb)


def _skill_score(tech_skills: list[str], wo_brand: str | None) -> float:
    if not wo_brand:
        return 0.5
    return 1.0 if _intersect_lower(tech_skills, [wo_brand]) else 0.0


def _distance_factor_and_km(
    tech_areas: list[str], wo_district: str | None
) -> tuple[float, float]:
    """district 完全命中 → (1.0, 0); 同縣市命中 → (0.6, 5);
    服務區域非空但無交集 → (0.2, 15); 候選技師無服務區資料 → (0.4, 30)。"""
    if not wo_district:
        return (0.4, 30.0)
    if not tech_areas:
        return (0.4, 30.0)
    if _intersect_lower(tech_areas, [wo_district]):
        return (1.0, 0.0)
    # 同縣市（前 2-3 字）命中
    wo_prefix = wo_district[:3].lower()
    for a in tech_areas:
        if a and a[:3].lower() == wo_prefix:
            return (0.6, 5.0)
    return (0.2, 15.0)


def _rating_factor(rating: float | None) -> float:
    if rating is None:
        return 0.0
    r = max(0.0, min(5.0, float(rating)))
    return r / 5.0


# FR-API-05：候選池 5→10→20km 漸進擴大門檻與最小池大小。
_PROGRESSIVE_RADII_KM = [5.0, 10.0, 20.0]
_MIN_DISPATCH_POOL = 3


def _apply_progressive_radius(
    candidates: list[dict], min_pool: int = _MIN_DISPATCH_POOL,
) -> list[dict]:
    """FR-API-05：以 gis_distance_km 逐級（5→10→20km）納入候選，達 min_pool 即停；
    三級仍不足 → 全納（含無座標者）。每候選標 radius_band_km。已 score 排序不變（僅決定
    「納入池」）。無座標者距離視為 ∞，只在最終全納級進入。"""
    if not candidates:
        return candidates

    def _km(c: dict) -> float:
        d = c.get("gis_distance_km")
        return float(d) if d is not None else float("inf")

    selected: list[dict] = []
    for radius in _PROGRESSIVE_RADII_KM:
        within = [c for c in candidates if _km(c) <= radius]
        if len(within) >= min_pool:
            selected = within
            break
    if not selected:
        selected = list(candidates)  # 三級不足 → 全納（radius_band 標 None＝>20km/無座標）

    for c in selected:
        km = _km(c)
        c["radius_band_km"] = next((r for r in _PROGRESSIVE_RADII_KM if km <= r), None)
    return selected


def _load_factor(active_load: int | None) -> float:
    """audit FR-API-05：當前在辦工單越少分越高。0 單=1.0，滿載(≥_LOAD_SATURATION)=0.0；
    None（查無資料）→中性 0.5。"""
    if active_load is None:
        return 0.5
    return max(0.0, 1.0 - min(active_load, _LOAD_SATURATION) / _LOAD_SATURATION)


def _fairness_factor(recent_jobs: int | None) -> float:
    """audit FR-API-05：近 7 日承接越少分越高（雨露均霑）。0 次=1.0；None→中性 0.5。"""
    if recent_jobs is None:
        return 0.5
    return 1.0 / (1.0 + max(0, recent_jobs))


def _availability_eta(online_state: str | None) -> int | None:
    """CR-0117 S5：ETA 粗估判 online_state。原版混域（'active' 是生命週期值、
    'busy' 是 online_state 值）→ 所有 active 技師一律回 15 分假 ETA。"""
    if online_state == "available":
        return 15
    if online_state == "busy":
        return 60
    return None


# ---------------------------------------------------------------------------
# Score breakdown rationale（給 admin 看「為什麼推薦」）
# ---------------------------------------------------------------------------


def _explain_skill(tech_skills: list[str], wo_brand: str | None) -> str:
    if not wo_brand:
        return "工單未指定品牌，技能匹配度回傳 fallback 0.5"
    if not tech_skills:
        return f"技師無技能資料，但工單需 {wo_brand}（fallback 0.5）"
    skills_lower = {s.lower() for s in tech_skills}
    if wo_brand.lower() in skills_lower:
        return f"技師認證品牌包含 {wo_brand} ✓"
    return f"技師未認證 {wo_brand} 品牌（其他技能：{', '.join(tech_skills[:3])}…）"


def _explain_distance(
    dist_km: float | None, district: str | None, tech_areas: list[str]
) -> str:
    if dist_km is None or district is None:
        return "工單或技師缺地理資訊（fallback 距離權重 0.5）"
    if dist_km <= 5:
        return f"技師服務區包含 {district}，距離極近 (~{dist_km}km)"
    if dist_km <= 15:
        return f"技師服務鄰近區（~{dist_km}km）"
    if dist_km <= 30:
        return f"技師服務同市但跨區（~{dist_km}km）"
    return f"距離較遠（~{dist_km}km），可能影響到場時間"


def _explain_rating(rating: float | None) -> str:
    if rating is None:
        return "尚無客戶評分資料（factor 0.0）"
    if rating >= 4.5:
        return f"高評分技師（{rating}/5）"
    if rating >= 3.5:
        return f"穩定評分（{rating}/5）"
    return f"評分偏低（{rating}/5），請審慎指派"


# CR-0051 / BR-M06 / G004-G005：生命週期「不可派工」狀態（未核准/停權/終止/退回）—
# 與「操作性不可用」（inactive/on_leave/circuit）區分；前者一律硬排除候選，不受 exclude_circuit 影響。
_DISPATCH_INELIGIBLE_STATUSES = {"pending_approval", "suspended", "terminated", "rejected"}


def _is_dispatch_eligible(status: str | None) -> bool:
    """BR-M06：技師是否具派工資格（生命週期狀態非未核准/停權/終止/退回）。"""
    return status not in _DISPATCH_INELIGIBLE_STATUSES


# CR-0061 / 審計#10：服務區中心點近似（無 PostGIS，用純 Haversine）。未知區 → 不算 GIS 距離。
_DISTRICT_CENTROIDS: dict[str, tuple[float, float]] = {
    "林口區": (25.0775, 121.3917), "新莊區": (25.0359, 121.4503),
    "板橋區": (25.0098, 121.4595), "三重區": (25.0617, 121.4870),
    "信義區": (25.0330, 121.5654), "大安區": (25.0263, 121.5436),
    "中山區": (25.0637, 121.5260), "中正區": (25.0320, 121.5180),
    "桃園區": (24.9937, 121.3010), "新北市": (25.0169, 121.4628),
    "台北市": (25.0330, 121.5654), "台北": (25.0330, 121.5654),
}


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    """兩經緯度球面距離（km）。"""
    import math
    r = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlmb = math.radians(float(lng2) - float(lng1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


async def _enrich_gis_performance(candidates: list[dict], wo_district: str | None) -> list[dict]:
    """CR-0061 審計#10#11：補真實 GIS 距離（Haversine 到區中心）+ 多維績效（on-time/acceptance），
    並以「績效加成」重排（主分數 + 小幅績效 bonus）。無座標/無區中心 → gis_distance 留 None，不破。"""
    if not candidates or not await _ensure_conn():
        return candidates
    ids = [c["technician"].get("id") for c in candidates if c.get("technician", {}).get("id")]
    if not ids:
        return candidates
    cur = await db_module._conn.execute(
        "SELECT id, latitude, longitude, on_time_rate, acceptance_rate FROM technicians "
        "WHERE id = ANY(%s::uuid[])", (ids,),
    )
    perf = {str(r[0]): r for r in await cur.fetchall()}
    centroid = _DISTRICT_CENTROIDS.get(wo_district or "")
    for c in candidates:
        tid = c["technician"].get("id")
        row = perf.get(tid)
        if not row:
            continue
        lat, lng, on_time, accept = row[1], row[2], row[3], row[4]
        gis_km = None
        if centroid is not None and lat is not None and lng is not None:
            gis_km = _haversine_km(centroid[0], centroid[1], lat, lng)
        on_time_f = float(on_time) if on_time is not None else None
        accept_f = float(accept) if accept is not None else None
        c["gis_distance_km"] = gis_km
        c["performance"] = {"on_time_rate": on_time_f, "acceptance_rate": accept_f}
        # 多維績效進排序：主分數 + 績效 bonus（最多 +20）；BR-M07-03
        if on_time_f is not None and accept_f is not None:
            c["performance_bonus"] = round(20 * (on_time_f + accept_f) / 2, 2)
            c["score"] = round(c.get("score", 0) + c["performance_bonus"], 2)
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates


async def _enrich_workload_fairness(candidates: list[dict], tenant_id: str) -> list[dict]:
    """audit FR-API-05：補「負載」與「公平」兩因子並計入排序、重排。

    負載 = 當前在辦工單數（status assigned/accepted/in_progress）；
    公平 = 近 7 日承接數（accepted_at 近 7 日）——越少分越高，工作機會分散。
    查詢失敗（欄位/連線）→ best-effort 略過（候選保留基礎分，不阻斷派工）。
    """
    if not candidates or not await _ensure_conn():
        return candidates
    ids = [c["technician"].get("id") for c in candidates if c.get("technician", {}).get("id")]
    if not ids:
        return candidates
    load: dict[str, int] = {}
    recent: dict[str, int] = {}
    try:
        cur = await db_module._conn.execute(
            "SELECT technician_id, COUNT(*) FROM work_orders "
            "WHERE technician_id = ANY(%s::uuid[]) "
            "  AND status IN ('assigned','accepted','in_progress') "
            "GROUP BY technician_id",
            (ids,),
        )
        load = {str(r[0]): int(r[1]) for r in await cur.fetchall()}
        cur = await db_module._conn.execute(
            "SELECT technician_id, COUNT(*) FROM work_orders "
            "WHERE technician_id = ANY(%s::uuid[]) "
            "  AND accepted_at >= NOW() - INTERVAL '7 days' "
            "GROUP BY technician_id",
            (ids,),
        )
        recent = {str(r[0]): int(r[1]) for r in await cur.fetchall()}
    except Exception:  # noqa: BLE001
        logger.exception("enrich_workload_fairness 查詢失敗；略過 load/fairness 加權")
        return candidates
    for c in candidates:
        tid = c["technician"].get("id")
        al = load.get(tid, 0)
        rj = recent.get(tid, 0)
        lf = _load_factor(al)
        ff = _fairness_factor(rj)
        load_contrib = round(_W_LOAD * lf * 100, 2)
        fair_contrib = round(_W_FAIRNESS * ff * 100, 2)
        c["active_load"] = al
        c["recent_jobs_7d"] = rj
        c["score"] = round(c.get("score", 0) + load_contrib + fair_contrib, 2)
        bd = c.setdefault("score_breakdown", {})
        bd["load"] = {
            "factor": round(lf, 2), "weight": _W_LOAD, "contribution": load_contrib,
            "rationale": f"當前在辦 {al} 張工單" + ("（滿載）" if al >= _LOAD_SATURATION else ""),
        }
        bd["fairness"] = {
            "factor": round(ff, 2), "weight": _W_FAIRNESS, "contribution": fair_contrib,
            "rationale": f"近 7 日承接 {rj} 次",
        }
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates


async def _brand_authorized_ids(brand: str | None) -> set[str] | None:
    """CR-0060 / BR-M07-01：回授權該品牌（未過期）的技師 id 集合。

    CR-0114 R4：technician_brand_authorization 是師傅身分域,改讀共用師傅庫
    authority（require_tech_conn;單庫 fallback 同顆連線,SQL 不變 → 行為不變）。

    **2026-07-31 fail-closed 修正（TC-DISPATCH-06）**：原本「該品牌無任何授權資料」
    也回 None,而 auto_match 與 _assert_brand_authorized 對 None **都選擇不阻擋** ——
    等於「還沒建授權名單的品牌 = 誰都可以派」。整合測試計畫 TC-DISPATCH-06 明文
    要求「無授權資料時 fail-closed **不得** fail-open」。

    實測影響面：本機 seed 的 technician_brand_authorization 只有 Generic / Kaadas /
    Philips / Samsung / Yale 五個品牌,但**所有** work_order 的 brand 都是 Chatlock
    → 修正前這道閘門對真實資料完全沒有作用。

    改後語意（三態收斂為兩態）：
      brand 為空       → None（**沒有品牌可判**,與「判了但沒人符合」不同,維持不阻擋;
                         品牌必填另由 _assert_dispatch_ready 把關）
      有 brand         → 一律回集合。查無授權列 = 空集合 = **誰都不符** = fail-closed。

    安全閥不變：手動派工仍可由主管帶 override_reason 強制通過
    （work_order_service._assert_brand_authorized,與報價 gate / 熔斷同一機制）。
    """
    if not brand:
        return None
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        "SELECT technician_id FROM technician_brand_authorization "
        "WHERE brand = %s AND authorized = TRUE "
        "  AND (cert_expires_at IS NULL OR cert_expires_at >= CURRENT_DATE)",
        (brand,),
    )
    rows = await cur.fetchall()
    if not rows:
        # 不再回 None —— 空集合才能讓下游「過濾」與「斷言」自然 fail-closed。
        # 記 warning:這是可行動的營運訊號（該品牌尚未建授權名單）,不該靜默。
        logger.warning(
            "品牌「%s」無任何有效授權技師 → 派工 fail-closed（需先建立品牌授權名單，"
            "或由主管帶 override_reason 手動派工）", brand,
        )
        return set()
    return {str(r[0]) for r in rows}


def _is_excluded_by_circuit(online_state: str | None) -> bool:
    """CR-0117 S5：操作性不可派判準 —— 判 online_state（可用性域）。

    原版收到「生命週期 status」（pending_approval/active/suspended/…）卻比對
    online_state 域值 → 永不命中，自動派工的熔斷/請假排除實為死邏輯。
    「inactive」在兩個域都不存在（死值）→ 移除；生命週期硬排除另由
    _is_dispatch_eligible 把關（兩者職責分立）。"""
    return online_state in {"on_leave", "circuit_breaker_open"}


async def _fetch_tenant_technicians(tenant_id: str) -> list[tuple]:
    # CR-0114 R4：師傅身分讀共用師傅庫 authority（require_tech_conn;單庫
    # fallback 同顆連線,SQL 不變 → 行為不變）。tenant 過濾保留（各品牌看自己
    # 租戶名下師傅;「全部啟用中可見」指不再因未授權而過濾,見 list_dispatch_candidates）。
    conn = await db_module.require_tech_conn()
    cur = await conn.execute(
        f"SELECT {_TECH_SELECT} FROM technicians t "
        f"WHERE t.tenant_id = %s::uuid",
        (tenant_id,),
    )
    return await cur.fetchall()


def _score_rows(
    rows: list[tuple],
    *,
    brand: str | None,
    district: str | None,
    skills_filter: list[str] | None = None,
    areas_filter: list[str] | None = None,
    rating_min: float | None = None,
    exclude_circuit: bool = True,
) -> list[dict]:
    """共用評分邏輯：技師 row → 含 score / distance / skill_match / eta 的 dict 列表。"""
    out: list[dict] = []
    for r in rows:
        status = r[9]  # 對齊 _TECH_SELECT（生命週期）
        online_state = r[11]  # 對齊 _TECH_SELECT（操作可用性,CR-0117 S5 熔斷判此欄）
        # CR-0051 / BR-M06：生命週期不可派工（未核准/停權/終止/退回）一律硬排除，不受 exclude_circuit 影響
        if not _is_dispatch_eligible(status):
            continue
        if exclude_circuit and _is_excluded_by_circuit(online_state):
            continue
        tech = _tech_row_to_dict(r)
        if skills_filter and not _intersect_lower(tech["skills"], skills_filter):
            continue
        if areas_filter and not _intersect_lower(tech["service_areas"], areas_filter):
            continue
        if rating_min is not None and tech["rating"] < float(rating_min):
            continue

        skill = _skill_score(tech["skills"], brand)
        dist_factor, dist_km = _distance_factor_and_km(tech["service_areas"], district)
        rating_f = _rating_factor(tech["rating"])
        # 各維度的「貢獻分」（0–40 / 0–30 / 0–30）
        skill_contrib = round(_W_SKILL * skill * 100, 2)
        distance_contrib = round(_W_DISTANCE * dist_factor * 100, 2)
        rating_contrib = round(_W_RATING * rating_f * 100, 2)
        score = round(skill_contrib + distance_contrib + rating_contrib, 2)
        out.append({
            "technician": tech,
            "score": score,
            "distance_km": dist_km,
            "skill_match": round(skill, 2),
            "availability_eta_minutes": _availability_eta(status),
            "score_breakdown": {
                "skill": {
                    "factor": round(skill, 2),
                    "weight": _W_SKILL,
                    "contribution": skill_contrib,
                    "rationale": _explain_skill(tech["skills"], brand),
                },
                "distance": {
                    "factor": round(dist_factor, 2),
                    "weight": _W_DISTANCE,
                    "contribution": distance_contrib,
                    "rationale": _explain_distance(dist_km, district, tech["service_areas"]),
                },
                "rating": {
                    "factor": round(rating_f, 2),
                    "weight": _W_RATING,
                    "contribution": rating_contrib,
                    "rationale": _explain_rating(tech["rating"]),
                },
            },
        })
    out.sort(key=lambda c: c["score"], reverse=True)
    return out


async def list_dispatch_candidates(
    *,
    tenant_id: str,
    work_order_id: str,
    skills_filter: list[str] | None = None,
    areas_filter: list[str] | None = None,
    levels_filter: list[str] | None = None,
    exclude_circuit: bool = True,
    rating_min: float | None = None,
) -> dict:
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 取工單的 brand / district 作為匹配依據
    cur = await db_module._conn.execute(
        "SELECT pc.brand, wo.customer_address "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (work_order_id, tenant_id),
    )
    wo_row = await cur.fetchone()
    if not wo_row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    wo_brand = wo_row[0]
    wo_address = wo_row[1] or ""

    from services.work_order_service import _parse_district
    wo_district = _parse_district(wo_address)

    rows = await _fetch_tenant_technicians(tenant_id)
    candidates = _score_rows(
        rows,
        brand=wo_brand,
        district=wo_district,
        skills_filter=skills_filter,
        areas_filter=areas_filter,
        rating_min=rating_min,
        exclude_circuit=exclude_circuit,
    )
    # CR-0114 R4（裁決 3）：鎖品牌授權由「過濾」改「標示」——全部啟用中師傅
    # 皆可見,每人標 brand_authorized（true/false/null）,已授權排前供人工挑選。
    # null = 該品牌無任何授權資料(無從判定;沿用原保守語意,不標未授權)。
    auth_ids = await _brand_authorized_ids(wo_brand)
    for c in candidates:
        if auth_ids is None:
            c["brand_authorized"] = None
        else:
            c["brand_authorized"] = c["technician"].get("id") in auth_ids
    # CR-0061 審計#10#11：補真實 GIS 距離 + 多維績效並重排
    candidates = await _enrich_gis_performance(candidates, wo_district)
    # audit FR-API-05：補負載/公平兩因子並重排（前三因子基礎分之上疊加）
    candidates = await _enrich_workload_fairness(candidates, tenant_id)
    # 已授權者優先（分數次之）;null（無授權資料）視同未授權排序權重,不影響可見性
    candidates.sort(key=lambda c: (c.get("brand_authorized") is True, c.get("score", 0)), reverse=True)
    return {
        "candidates": candidates,
        "total": len(candidates),
        "auto_dispatch_attempts": [],
    }


async def auto_match_dispatch(
    *,
    tenant_id: str,
    problem_card_id: str,
    urgency: str = "normal",
    max_candidates: int = 3,
) -> dict:
    """autoMatchDispatch — 依 problem_card 的 brand 與最新 WO 地址計算候選。

    回傳 DispatchAutoMatchResponse schema（DispatchCandidate.score 介於 0~1）。
    無關聯 WO 時 district 為空，僅以 skill + rating 評分；
    urgency='emergency' 時將 score 提升 5%（至多 1.0）以便重排。
    """
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    cur = await db_module._conn.execute(
        "SELECT pc.brand "
        "FROM problem_cards pc "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND COALESCE(pc.tenant_id, u.tenant_id) = %s::uuid",
        (problem_card_id, tenant_id),
    )
    pc_row = await cur.fetchone()
    if not pc_row:
        raise ApiError("NOT_FOUND", "Problem card not found", 404)
    pc_brand = pc_row[0]

    # 取此 PC 最新 WO 的地址（若有）
    cur = await db_module._conn.execute(
        "SELECT customer_address FROM work_orders "
        "WHERE problem_card_id = %s::uuid "
        "ORDER BY created_at DESC LIMIT 1",
        (problem_card_id,),
    )
    wo_row = await cur.fetchone()
    wo_address = (wo_row[0] if wo_row else "") or ""

    from services.work_order_service import _parse_district
    pc_district = _parse_district(wo_address)

    rows = await _fetch_tenant_technicians(tenant_id)
    scored = _score_rows(rows, brand=pc_brand, district=pc_district)
    # CR-0114 R4（裁決 7）：**自動派工維持只選已授權**——人工派工可挑未授權
    # (list_dispatch_candidates 標示可見),但自動指派不該自行派給沒修過該鎖品牌
    # 的師傅。無授權資料(None)時保守不過濾(沿用原語意)。
    _auth_ids = await _brand_authorized_ids(pc_brand)
    if _auth_ids is not None:
        scored = [c for c in scored if c["technician"].get("id") in _auth_ids]
    # CR-0061：GIS 距離 + 多維績效重排
    scored = await _enrich_gis_performance(scored, pc_district)
    # audit FR-API-05：補負載/公平兩因子並重排
    scored = await _enrich_workload_fairness(scored, tenant_id)
    # FR-API-05：候選池 5→10→20km 漸進擴大（近者優先，不足才擴半徑）
    scored = _apply_progressive_radius(scored)

    boost = 1.05 if urgency == "emergency" else 1.0
    candidates: list[dict] = []
    for c in scored[:max_candidates]:
        s_norm = min(1.0, (c["score"] / 100.0) * boost)
        t = c["technician"]
        candidates.append({
            "technician_id": t["id"],
            "technician_name": t.get("name") or None,
            "score": round(s_norm, 4),
            "distance_km": c.get("distance_km"),
            "eta_minutes": c.get("availability_eta_minutes"),
            "rating": t.get("rating"),
        })
    return {"candidates": candidates}


async def assign_dispatch(
    *,
    tenant_id: str,
    work_order_id: str,
    technician_id: str,
    override_reason: str | None = None,
) -> dict:
    """assignDispatch — body 版本的指派；複用 work_order_service.assign_order。

    語義對齊 /work-orders/{id}/assign，差別僅在工單 id 來源。
    """
    from services.work_order_service import assign_order

    return await assign_order(
        tenant_id=tenant_id,
        wo_id=work_order_id,
        technician_id=technician_id,
        reason_code="other",
        reason_text=override_reason,
    )


async def get_candidate_detail(
    *,
    tenant_id: str,
    work_order_id: str,
    technician_id: str,
) -> dict:
    """A37 派工人工介入 — 單一候選技師詳情。

    給 admin drawer 顯示，組合：
    - 基本資料 (get_technician)
    - 當週負載熱圖 (get_technician_workload_heatmap, 若可用)
    - 對該工單的 dispatch context (distance_km / score / eta)

    無新 SQL — 重用既有 service。
    """
    from services.technician_service import get_technician
    try:
        from services.technician_service import get_technician_workload_heatmap
    except ImportError:
        get_technician_workload_heatmap = None  # type: ignore

    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)

    # 基本資料
    tech = await get_technician(
        tenant_id=tenant_id, technician_id=technician_id,
    )

    # 取工單 brand/district 作 dispatch context
    cur = await db_module._conn.execute(
        "SELECT pc.brand, wo.customer_address "
        "FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (work_order_id, tenant_id),
    )
    wo_row = await cur.fetchone()
    if not wo_row:
        raise ApiError("NOT_FOUND", "Work order not found", 404)
    wo_brand = wo_row[0]
    wo_address = wo_row[1] or ""

    from services.work_order_service import _parse_district
    wo_district = _parse_district(wo_address)

    skills = tech.get("capabilities") or tech.get("skills") or []
    regions = tech.get("regions") or tech.get("areas") or []
    rating = tech.get("rating")
    status = tech.get("status")
    # CR-0117 S5：熔斷/ETA 判操作可用性（availability=online_state），生命週期另判
    availability = tech.get("availability")

    dispatch_context = {
        "work_order_id": work_order_id,
        "wo_brand": wo_brand,
        "wo_district": wo_district,
        "skill_match": _explain_skill(skills, wo_brand),
        "distance_explain": _explain_distance(None, wo_district, regions),
        "rating_explain": _explain_rating(rating),
        "excluded_by_circuit": _is_excluded_by_circuit(availability),
        "dispatch_eligible": _is_dispatch_eligible(status),  # CR-0051 BR-M06 生命週期資格
        "eta_minutes": _availability_eta(availability),
    }

    # 當週負載 (best-effort, 失敗不影響主資料)
    workload = None
    if get_technician_workload_heatmap is not None:
        try:
            workload = await get_technician_workload_heatmap(
                tenant_id=tenant_id, technician_id=technician_id,
            )
        except Exception:  # noqa: BLE001
            workload = None

    return {
        "technician": tech,
        "dispatch_context": dispatch_context,
        "workload_heatmap": workload,
    }
