"""refinery 模組 License 開通 gate（CR-0166 R3 / ADR-018）。

refinery 為 License 附加模組——租戶須開通 'refinery' 才可煉製。開通狀態存平台庫
tenant.entitled_modules（平台 console 管理，CR-0166 R3）。

連線：PLATFORM_POSTGRES_URI（平台庫）。未設定時 fail-open（單庫 dev/本機，比照
tech_mirror 單庫 fallback）——避免本機開發被 License 擋住；prod 設 PLATFORM_POSTGRES_URI
即生效。REFINERY_SKIP_ENTITLEMENT=1 亦可強制略過（測試/緊急）。
"""

import os
import uuid

import psycopg


class ModuleNotEntitledError(RuntimeError):
    """租戶未開通 refinery 模組（或 License 過期）。"""


def _platform_uri() -> str | None:
    return os.getenv("PLATFORM_POSTGRES_URI")


def is_refinery_entitled(tenant_id: str) -> bool:
    """查平台庫 tenant.entitled_modules 是否含 'refinery' 且 License 未過期。
    平台庫未配置 → True（fail-open，本機 dev）。查無租戶/DB 失敗 → False（fail-closed）。"""
    if os.getenv("REFINERY_SKIP_ENTITLEMENT") == "1":
        return True
    uri = _platform_uri()
    if not uri:
        return True  # 單庫 dev：無平台庫，不擋
    try:
        uuid.UUID(str(tenant_id))
    except (ValueError, TypeError):
        return False
    try:
        with psycopg.connect(uri) as conn:
            cur = conn.execute(
                "SELECT entitled_modules @> '[\"refinery\"]'::jsonb, "
                "  (license_expires_at IS NULL OR license_expires_at > NOW()) "
                "FROM tenant WHERE id = %s::uuid",
                (tenant_id,))
            row = cur.fetchone()
    except Exception:  # noqa: BLE001 — DB 失敗 → fail-closed（不誤放未開通租戶）
        return False
    if not row:
        return False
    return bool(row[0]) and bool(row[1])


def assert_refinery_entitled(tenant_id: str) -> None:
    """未開通/過期 → raise ModuleNotEntitledError（run_intake 入口 gate）。"""
    if not is_refinery_entitled(tenant_id):
        raise ModuleNotEntitledError(
            f"租戶 {tenant_id} 未開通 refinery 模組或 License 已過期"
            "（平台 console → 租戶 License 開通）。設 REFINERY_SKIP_ENTITLEMENT=1 可略過。")
