"""Evidence Package 聚合 service（CR-0055 / Q022-Q024 / BR-M09）。

把單一 WorkOrder 分散的完工證據（媒體照片 / 雙方簽名 / 到場+門檢事件）聚合為單一唯讀檢視，
供後台稽核 / 結案證據包。媒體依角色可見性過濾（沿 media_service 規則）。
"""

from __future__ import annotations

import core.db as db_module
from core.errors import ApiError


async def get_evidence_package(*, tenant_id: str, wo_id: str, role: str | None = None) -> dict:
    """聚合 WO 證據包：media（角色過濾）+ signatures + arrival/door_check 事件 + summary。"""
    from services import media_service, work_order_service

    # list_work_order_events 內含 _fetch_status_for_update → 驗 tenant + WO 存在（404/跨租戶擋）
    events = await work_order_service.list_work_order_events(tenant_id=tenant_id, wo_id=wo_id)
    media = await media_service.list_media_for_work_order(
        tenant_id=tenant_id, work_order_id=wo_id, role=role,
    )

    if not await db_module._ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    cur = await db_module._conn.execute(
        "SELECT signer_role, signature_method, signed_at FROM digital_signatures "
        "WHERE document_type = 'work_order' AND document_id = %s::uuid ORDER BY signed_at",
        (wo_id,),
    )
    sig_rows = await cur.fetchall()
    signatures = [
        {"signer_role": r[0], "method": r[1],
         "signed_at": r[2].isoformat() if r[2] else None}
        for r in sig_rows
    ]

    media_items = media.get("items", []) if isinstance(media, dict) else []
    ev_items = events.get("items", []) if isinstance(events, dict) else []

    def _ev_type(e: dict) -> str:
        return e.get("event_type") or e.get("type") or ""

    return {
        "work_order_id": wo_id,
        "media": media_items,
        "signatures": signatures,
        "events": ev_items,
        "summary": {
            "photo_count": len(media_items),
            "signature_count": len(signatures),
            "has_customer_signature": any(s["signer_role"] == "customer" for s in signatures),
            "has_technician_signature": any(s["signer_role"] == "technician" for s in signatures),
            "has_arrival": any(_ev_type(e) == "arrival" for e in ev_items),
            "has_door_check": any(_ev_type(e) == "door_check" for e in ev_items),
        },
    }
