"""Dispatch candidates — listDispatchCandidates。

operationId 對齊 openapi.yaml：listDispatchCandidates

設計：
  - 依工單 brand / district 對候選技師排序
  - 綜合分（0~100）= 0.4 × skill_match + 0.3 × distance_factor + 0.3 × rating_factor
      skill_match     ∈ [0,1]：brand 命中 +1.0；無 brand 資訊 fallback 0.5
      distance_factor ∈ [0,1]：district 命中 1.0；服務區域命中該縣市 0.6；無交集 0.2
      rating_factor   ∈ [0,1]：rating / 5
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


_W_SKILL = 0.4
_W_DISTANCE = 0.3
_W_RATING = 0.3


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


def _availability_eta(status: str | None) -> int | None:
    if status == "active":
        return 15
    if status == "busy":
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


def _is_excluded_by_circuit(status: str | None) -> bool:
    """暫無 circuit_breaker_until 欄；以 status 排除明顯不可派的狀態。"""
    return status in {"inactive", "on_leave", "circuit_breaker_open"}


async def _fetch_tenant_technicians(tenant_id: str) -> list[tuple]:
    cur = await db_module._conn.execute(
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
        status = r[9]  # 對齊 _TECH_SELECT
        if exclude_circuit and _is_excluded_by_circuit(status):
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
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND u.tenant_id = %s::uuid",
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
        "JOIN conversations c ON pc.conversation_id = c.id "
        "JOIN users u ON c.user_id = u.id "
        "WHERE pc.id = %s::uuid AND u.tenant_id = %s::uuid",
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
