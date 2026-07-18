"""CR-0033 免責同意 service。

三段免責文本（藍圖模組 4「施工免責與合規」佔位，**待法務 sign-off**）+ work_order_consents
upsert 紀錄。文本以常數存（非 legal_text_versions 版本主檔，避免過度設計）；text_version 記快照。

安全不變式：本 service 只處理法律文字 + 同意旗標，**不接觸任何金額/成本欄位**。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import core.db as db_module
from core.db import _ensure_conn
from core.errors import ApiError

logger = logging.getLogger("api.consent_service")

# 免責文本版本（待法務定稿後升版；§8-Q5 工單記當時版本）
TEXT_VERSION = "blueprint-draft-2026-06"

# 三段免責文本（藍圖模組 4；佔位語意，正式措辭待法務 —— CR-0033 §8 Q1）
CONSENT_TEXTS = [
    {
        "consent_type": "new_installation",
        "title": "新機安裝同意聲明",
        "body": "本人了解新鎖安裝涉及門板開孔、鑽洞與施工噪音之必然性，並同意施作。"
                "溫馨提醒：緊急備用鑰匙切勿放置於室內或車上。（待法務定稿）",
    },
    {
        "consent_type": "lock_destruction",
        "title": "破壞鎖施工免責特別說明",
        "body": "若需破壞鎖方能解鎖，本人同意施作；若非產品故障（人為操作不當所致），"
                "破壞及門扇重置費用由本人自負。（待法務定稿）",
    },
    {
        "consent_type": "personal_data",
        "title": "個人資料保護法條款",
        "body": "本人授權品牌方及協力廠商，基於維修與報價目的，於必要範圍內蒐集、處理及利用本人個資。"
                "（待法務定稿）",
    },
]
_VALID_TYPES = {c["consent_type"] for c in CONSENT_TEXTS}


async def _conn():
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    return db_module._conn


async def _assert_wo_in_tenant(conn, work_order_id: str, tenant_id: str | None) -> None:
    """defense-in-depth：驗 work_order 屬該租戶（除 token HMAC 綁定外的 DB 層守門）。

    沿 work_orders→problem_cards→conversations→users.tenant_id JOIN 鏈（同 invoice_service）。
    tenant_id 為 None（舊 token 無 scope）→ 跳過（依賴 token 簽章）。
    """
    if not tenant_id:
        return
    row = await (await conn.execute(
        "SELECT 1 FROM work_orders wo "
        "JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "LEFT JOIN conversations c ON pc.conversation_id = c.id "
        "LEFT JOIN users u ON c.user_id = u.id "
        "WHERE wo.id = %s::uuid AND COALESCE(wo.tenant_id, u.tenant_id) = %s::uuid",
        (work_order_id, tenant_id))).fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "work order not found", 404)


async def get_consents(*, work_order_id: str, tenant_id: str | None = None) -> dict:
    """回三段文本 + 各自同意狀態 + 簽署當時文本版本（未紀錄者 accepted=False）。"""
    conn = await _conn()
    await _assert_wo_in_tenant(conn, work_order_id, tenant_id)
    rows = await (await conn.execute(
        "SELECT consent_type, accepted, accepted_at, text_version FROM work_order_consents "
        "WHERE work_order_id = %s::uuid", (work_order_id,))).fetchall()
    status = {r[0]: {"accepted": bool(r[1]), "accepted_at": r[2].isoformat() if r[2] else None,
                     "text_version": r[3]} for r in rows}
    items = [{
        **c,
        "accepted": status.get(c["consent_type"], {}).get("accepted", False),
        "accepted_at": status.get(c["consent_type"], {}).get("accepted_at"),
        # 簽署當時版本快照（§8-Q5）；未紀錄者用當前版本
        "text_version": status.get(c["consent_type"], {}).get("text_version", TEXT_VERSION),
    } for c in CONSENT_TEXTS]
    return {"text_version": TEXT_VERSION, "consents": items}


async def record_consents(
    *, work_order_id: str, consents: dict, ip_address: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    """記錄客戶免責同意（upsert，UNIQUE(work_order_id, consent_type) 冪等）。

    Args:
        consents: {consent_type: bool}；未知 type / 非 bool value → 422。
    """
    if not isinstance(consents, dict) or not consents:
        raise ApiError("VALIDATION_ERROR", "consents must be a non-empty map", 422)
    unknown = set(consents) - _VALID_TYPES
    if unknown:
        raise ApiError("VALIDATION_ERROR", f"unknown consent_type: {sorted(unknown)}", 422)
    # 嚴格 bool（防 bool('false')==True 之類強制轉換漏洞）
    if any(not isinstance(v, bool) for v in consents.values()):
        raise ApiError("VALIDATION_ERROR", "consent values must be boolean", 422)

    conn = await _conn()
    await _assert_wo_in_tenant(conn, work_order_id, tenant_id)
    now = datetime.now(timezone.utc)
    for ctype, accepted in consents.items():
        await conn.execute(
            "INSERT INTO work_order_consents "
            "  (work_order_id, consent_type, accepted, accepted_at, text_version, ip_address) "
            "VALUES (%s::uuid, %s, %s, %s, %s, %s) "
            "ON CONFLICT (work_order_id, consent_type) DO UPDATE SET "
            "  accepted = EXCLUDED.accepted, accepted_at = EXCLUDED.accepted_at, "
            "  text_version = EXCLUDED.text_version, ip_address = EXCLUDED.ip_address",
            (work_order_id, ctype, bool(accepted), now if accepted else None, TEXT_VERSION, ip_address))
    logger.info("consents recorded: wo=%s types=%s ip=%s", work_order_id, list(consents), ip_address)
    return await get_consents(work_order_id=work_order_id, tenant_id=tenant_id)
