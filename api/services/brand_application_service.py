"""品牌申請服務(CR-0114 R2)— landing 公開申請 + platform console 審核。

設計要點(業主裁決 2:核准後開站**純手動**):
  - 申請 = 意向書:不建帳號、不收密碼;核准只翻狀態 + 產「開站指引」純文字,
    實際開站由工程手動跑部署腳本。
  - 資料住平台庫(require_platform_conn;未配置時 fallback 主連線)。
  - 公開表單限流:DB 計數 per-IP 滑動視窗(對齊 password_reset 的 DB 計數
    模式,不引新 infra;in-memory 會因重啟歸零)。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import core.db as db_module
from core.errors import ApiError
from services import platform_tenant_service

logger = logging.getLogger("api.brand_application")

#: 同一 IP 每小時最多申請件數(公開表單防灌爆;正常申請人一件就夠)
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW_MINUTES = 60

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,29}$")

_TYPE_LABEL = {"brand": "品牌商", "locksmith": "鎖店", "distributor": "經銷商"}


async def _conn():
    try:
        return await db_module.require_platform_conn()
    except RuntimeError:
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)


def _row_to_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "application_type": row[1],
        "company_name": row[2],
        "contact_name": row[3],
        "tax_id": row[4],
        "phone": row[5],
        "email": row[6],
        "address": row[7],
        "notes": row[8],
        "status": row[9],
        "slug": row[10],
        "review_notes": row[11],
        "reviewed_at": row[12].isoformat() if row[12] else None,
        "created_at": row[13].isoformat() if row[13] else None,
        # 業界補充欄位(additive)
        "website": row[14],
        "coverage_regions": row[15],
        "store_count": row[16],
        "expected_monthly_orders": row[17],
        "main_brands": row[18],
        "referral_source": row[19],
    }


_SELECT_COLS = (
    "id, application_type, company_name, contact_name, tax_id, phone, email, "
    "address, notes, status, slug, review_notes, reviewed_at, created_at, "
    "website, coverage_regions, store_count, expected_monthly_orders, "
    "main_brands, referral_source"
)


async def submit(
    *,
    application_type: str,
    company_name: str,
    contact_name: str,
    tax_id: str,
    phone: str,
    email: str,
    address: str | None,
    notes: str | None,
    website: str | None = None,
    coverage_regions: str | None = None,
    store_count: int | None = None,
    expected_monthly_orders: str | None = None,
    main_brands: str | None = None,
    referral_source: str | None = None,
    request_ip: str | None,
) -> dict:
    """公開申請(landing 品牌 CTA)。回 {id, status}。"""
    conn = await _conn()

    # per-IP 限流(DB 計數,重啟不歸零)
    if request_ip:
        window_start = datetime.now(timezone.utc) - timedelta(minutes=_RATE_LIMIT_WINDOW_MINUTES)
        cur = await conn.execute(
            "SELECT COUNT(*) FROM brand_applications WHERE submitted_ip = %s AND created_at > %s",
            (request_ip, window_start),
        )
        recent = (await cur.fetchone())[0]
        if recent >= _RATE_LIMIT_MAX:
            logger.warning("brand_application 限流命中 ip=%s recent=%s", request_ip, recent)
            raise ApiError("RATE_LIMITED", "申請次數過多，請稍後再試", 429)

    # 同 email 待審去重(部分唯一索引為最終防線,先查給友善訊息)
    cur = await conn.execute(
        "SELECT 1 FROM brand_applications WHERE email = %s AND status = 'pending' LIMIT 1",
        (email,),
    )
    if await cur.fetchone():
        raise ApiError("APPLICATION_EXISTS", "此 Email 已有待審核的申請，平台將盡快與您聯絡", 409)

    cur = await conn.execute(
        "INSERT INTO brand_applications "
        "(application_type, company_name, contact_name, tax_id, phone, email, address, notes, "
        "website, coverage_regions, store_count, expected_monthly_orders, main_brands, referral_source, "
        "submitted_ip) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            application_type,
            company_name.strip(),
            contact_name.strip(),
            tax_id.strip(),
            phone.strip(),
            email.strip(),
            (address or "").strip() or None,
            (notes or "").strip() or None,
            (website or "").strip() or None,
            (coverage_regions or "").strip() or None,
            store_count,
            (expected_monthly_orders or "").strip() or None,
            (main_brands or "").strip() or None,
            (referral_source or "").strip() or None,
            request_ip,
        ),
    )
    app_id = str((await cur.fetchone())[0])
    logger.info("brand_application 新申請 id=%s type=%s company=%s", app_id, application_type, company_name)
    return {
        "data": {"id": app_id, "status": "pending"},
        "message": "申請已送出，平台審核後將與您聯絡",
    }


async def list_applications(status: str | None = None) -> dict:
    conn = await _conn()
    if status:
        cur = await conn.execute(
            f"SELECT {_SELECT_COLS} FROM brand_applications WHERE status = %s ORDER BY created_at DESC",
            (status,),
        )
    else:
        cur = await conn.execute(
            f"SELECT {_SELECT_COLS} FROM brand_applications ORDER BY created_at DESC"
        )
    rows = await cur.fetchall()
    return {"data": [_row_to_dict(r) for r in rows], "message": None}


def _onboarding_guide(app: dict) -> str:
    """核准後的手動開站指引(裁決 2:只產文字,不自動化)。

    以 scripts/deploy/brands/locksmart.env 為參考模板列建議值;埠位需依
    當時環境挑未占用值,故列預設+提醒而非武斷指定。
    """
    slug = app["slug"]
    return (
        f"品牌開站指引 — {app['company_name']}({_TYPE_LABEL.get(app['application_type'], app['application_type'])},代號 {slug})\n"
        f"\n"
        f"[1] 建品牌參數檔 scripts/deploy/brands/{slug}.env(參考 locksmart.env):\n"
        f"    PROJECT_ID=lock-ai-{slug}          # 一品牌一 GCP 專案\n"
        f"    REGION=asia-east1\n"
        f"    API_SERVICE_NAME=lock-api-{slug}\n"
        f"    WEB_SERVICE_NAME=lock-web-{slug}\n"
        f"    CLOUDSQL_INSTANCE=lock-sql-{slug}\n"
        f"    DB_USER=lock-ai / DB_NAME=lock-ai-db\n"
        f"    AGENT_TENANT_ID=<新租戶 UUID>\n"
        f"\n"
        f"[2] 本機/自架 compose 開站(埠位挑未占用;預設品牌用 5433/8001/8000/3000):\n"
        f"    BRAND={slug} DB_PORT=<port> API_PORT=<port> AGENT_PORT=<port> WEB_PORT=<port> \\\n"
        f"      docker compose -f compose/docker-compose.dispatch.yml up -d --build\n"
        f"    BRAND={slug} docker compose -f compose/docker-compose.dispatch.yml --profile init run --rm db-init\n"
        f"\n"
        f"[3] 接技師共用庫(CR-0112 方法 B 雙庫;不設則單庫 fallback):\n"
        f"    TECH_POSTGRES_URI=postgresql://lock:0000@tech-db:5432/lock_tech \\\n"
        f"      BRAND={slug} docker compose -f compose/docker-compose.dispatch.yml up -d api\n"
        f"\n"
        f"[4] 建立品牌 Admin 帳號後,聯絡申請人開通:\n"
        f"    {app['contact_name']} <{app['email']}> {app['phone']}\n"
        f"    公司:{app['company_name']}(統編 {app['tax_id']})\n"
    )


async def approve(
    *, app_id: str, reviewer_id: str, slug: str | None = None, review_notes: str | None = None
) -> dict:
    """核准:CAS pending→approved,回申請資料 + onboarding_guide 文字。"""
    conn = await _conn()

    final_slug = (slug or "").strip().lower() or f"brand-{app_id[:8]}"
    if not _SLUG_RE.match(final_slug):
        raise ApiError(
            "VALIDATION_ERROR",
            "品牌代號需為 3-30 字元的小寫英數與連字號,且以字母開頭",
            422,
        )

    cur = await conn.execute(
        "UPDATE brand_applications SET status='approved', slug=%s, review_notes=%s, "
        "reviewed_by=%s::uuid, reviewed_at=NOW() "
        "WHERE id=%s::uuid AND status='pending' "
        f"RETURNING {_SELECT_COLS}",
        (final_slug, (review_notes or "").strip() or None, reviewer_id, app_id),
    )
    row = await cur.fetchone()
    if not row:
        await _raise_not_pending(conn, app_id)
    app = _row_to_dict(row)
    logger.info("brand_application 核准 id=%s slug=%s by=%s", app_id, final_slug, reviewer_id)

    # CR-0118:核准後登錄租戶 registry(fail-soft:登錄失敗不擋核准,loud log)。
    tenant_id: str | None = None
    try:
        tenant_id = await platform_tenant_service.create_from_application(app)
    except Exception:  # noqa: BLE001 — registry 登錄失敗不可回滾已生效的核准
        logger.exception("brand_application 核准後租戶登錄失敗 app_id=%s slug=%s", app_id, final_slug)

    return {
        "data": {**app, "tenant_id": tenant_id, "onboarding_guide": _onboarding_guide(app)},
        "message": "已核准;開站流程請依指引手動執行",
    }


async def reject(*, app_id: str, reviewer_id: str, reason: str) -> dict:
    """拒絕:CAS pending→rejected(reason 必填)。"""
    if not reason or len(reason.strip()) < 3:
        raise ApiError("VALIDATION_ERROR", "拒絕原因至少 3 個字", 422)
    conn = await _conn()
    cur = await conn.execute(
        "UPDATE brand_applications SET status='rejected', review_notes=%s, "
        "reviewed_by=%s::uuid, reviewed_at=NOW() "
        "WHERE id=%s::uuid AND status='pending' "
        f"RETURNING {_SELECT_COLS}",
        (reason.strip(), reviewer_id, app_id),
    )
    row = await cur.fetchone()
    if not row:
        await _raise_not_pending(conn, app_id)
    logger.info("brand_application 拒絕 id=%s by=%s", app_id, reviewer_id)
    return {"data": _row_to_dict(row), "message": "已拒絕"}


async def _raise_not_pending(conn, app_id: str) -> None:
    """CAS 失敗時區分 404(不存在)與 409(非待審)。"""
    cur = await conn.execute(
        "SELECT status FROM brand_applications WHERE id = %s::uuid", (app_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Application not found", 404)
    raise ApiError("STATE_CONFLICT", f"Application is {row[0]}, not pending", 409)
