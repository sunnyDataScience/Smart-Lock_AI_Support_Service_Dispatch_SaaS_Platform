"""Smart Lock AI — Admin REST API entrypoint.

啟動：cd api && uvicorn main:app --reload --port 8001
所有設定從 config.toml 讀取，敏感值從 .env。
"""

import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# 載入專案根目錄 .env（與 agent/ 共用）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import load_config
from core.db import init_db, close_db, healthcheck
from core.errors import register_exception_handlers
from core.idempotency import IdempotencyReplay, handle_idempotency_replay
from middleware.request_id import RequestIdMiddleware
from routers import auth as auth_router
from routers import notifications as notifications_router
from routers import system_config as system_config_router
from routers import kb_cases as kb_cases_router
from routers import kb_manuals as kb_manuals_router
from routers import sop_drafts as sop_drafts_router
from routers import audit_logs as audit_logs_router
from routers import conversations as conversations_router
from routers import dashboard as dashboard_router
from routers import problem_cards as problem_cards_router
from routers import work_orders as work_orders_router
from routers import work_order_actions as work_order_actions_router
from routers import technicians as technicians_router
from routers import admin_schedule as admin_schedule_router
from routers import media as media_router
from routers import dispatch_logs as dispatch_logs_router
from routers import dispatch as dispatch_router
from routers import settlements as settlements_router
from routers import reconciliations as reconciliations_router
from routers import invoices as invoices_router
from routers import refunds as refunds_router
from routers import warranty_claims as warranty_claims_router
from routers import disputes as disputes_router
from routers import revenue as revenue_router
from routers import pricing_rules as pricing_rules_router
from routers import customers as customers_router
from routers import roles as roles_router
from routers import inventory as inventory_router
from routers import reports_kpi as reports_kpi_router
from routers import reports_export as reports_export_router
from routers import resolution as resolution_router
from routers import kb_export as kb_export_router
from routers import sentiment_alerts as sentiment_alerts_router
from routers import vouchers as vouchers_router
from routers import family_reviews as family_reviews_router
from routers import data_corrections as data_corrections_router  # CR-0001 §3 review queue
from routers import public as public_router  # Q3=C / Q9=B 共用機制
from routers import cancellation as cancellation_router  # spec-alignment P1-A (ADR-0102, tenant-scoped)

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

cfg = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: 連線 DB → 啟動 monitors → 關閉。"""
    await init_db(cfg.database)
    # 啟動背景監測（單機 in-memory；多 worker 須改 distributed scheduler）
    from realtime.inventory_monitor import monitor as inventory_monitor
    from realtime.sla_monitor import monitor as sla_monitor

    inventory_monitor.start()
    sla_monitor.start()
    logger.info("API service ready (port=%s)", cfg.system["port"])
    yield
    await sla_monitor.stop()
    await inventory_monitor.stop()
    await close_db()
    logger.info("API service stopped")


app = FastAPI(
    title="Smart Lock AI — Admin REST API",
    version="0.2.0",
    description=(
        "Phase 1 MVP. Contract SSOT (frozen V1.1): docs/architecture/api/openapi.yaml "
        "+ openapi-smart-lock-saas.yaml. NOTE: legacy /api/v1 routes were generated from the "
        "now-deleted docs/02-design/specs/openapi.yaml; spec-alignment migration in progress "
        "(see docs/_audit/spec-code-gap-audit-2026-06-01.md)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.system.get("cors_origins", ["http://localhost:3000"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "RateLimit-Limit", "RateLimit-Remaining", "RateLimit-Reset"],
)
app.add_middleware(RequestIdMiddleware)

register_exception_handlers(app)
app.add_exception_handler(IdempotencyReplay, handle_idempotency_replay)

app.include_router(auth_router.router, prefix="/api/v1", tags=["auth"])
app.include_router(notifications_router.router, prefix="/api/v1", tags=["realtime"])
app.include_router(system_config_router.router, prefix="/api/v1", tags=["user_management"])
app.include_router(kb_cases_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(kb_manuals_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(sop_drafts_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(family_reviews_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(audit_logs_router.router, prefix="/api/v1", tags=["observability"])
app.include_router(data_corrections_router.router, prefix="/api/v1", tags=["knowledge_base"])
app.include_router(conversations_router.router, prefix="/api/v1", tags=["customer_service"])
app.include_router(sentiment_alerts_router.router, prefix="/api/v1", tags=["customer_service"])
app.include_router(dashboard_router.router, prefix="/api/v1", tags=["reports"])
app.include_router(problem_cards_router.router, prefix="/api/v1", tags=["customer_service"])
app.include_router(work_orders_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(work_order_actions_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(technicians_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(admin_schedule_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(media_router.router, prefix="/api/v1", tags=["media"])
app.include_router(dispatch_logs_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(dispatch_router.router, prefix="/api/v1", tags=["dispatch"])
app.include_router(settlements_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(vouchers_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(reconciliations_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(invoices_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(refunds_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(warranty_claims_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(disputes_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(revenue_router.router, prefix="/api/v1", tags=["reports"])
app.include_router(pricing_rules_router.router, prefix="/api/v1", tags=["accounting"])
app.include_router(customers_router.router, prefix="/api/v1", tags=["customer_service"])
app.include_router(roles_router.router, prefix="/api/v1", tags=["user_management"])
app.include_router(inventory_router.router, prefix="/api/v1", tags=["inventory"])
app.include_router(reports_kpi_router.router, prefix="/api/v1", tags=["reports"])
app.include_router(reports_export_router.router, prefix="/api/v1", tags=["reports"])
app.include_router(resolution_router.router, prefix="/api/v1", tags=["customer_service"])
app.include_router(kb_export_router.router, prefix="/api/v1", tags=["knowledge_base"])
# Q3=C / Q9=B 共用機制：消費者匿名 token endpoints（無需登入）
# Auth middleware 應在 path 前綴 /api/v1/public/ 略過 bearer 驗證
app.include_router(public_router.router, prefix="/api/v1", tags=["public"])
# spec-alignment P1-A：tenant-scoped 取消端點，無 /api/v1 前綴以對齊 frozen spec path
app.include_router(cancellation_router.router, tags=["M11 AR / Payment"])


@app.get("/health")
async def health():
    """Health check — DB 連線存活檢測。"""
    db_ok = await healthcheck()
    from fastapi.responses import JSONResponse
    status = "ok" if db_ok else "degraded"
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={"status": status, "version": app.version, "checks": {"db": "ok" if db_ok else "disconnected"}},
    )


# =============================================================================
# WebSocket realtime endpoints（pub-sub via in-memory hub）
# =============================================================================
# 對應 docs/02-design/specs/asyncapi.yaml 10 個頻道（diagnostics 為 SSE，另開）
# 客戶端透過 query 帶 access_token + tenant_id 認證（瀏覽器 WS 不支援 custom header）

from fastapi import WebSocket, WebSocketDisconnect, Query  # noqa: E402

from realtime.ws_hub import hub, verify_ws_token, authorize_channel, WSAuthError  # noqa: E402


# admin 類頻道允許的角色（依需求調整）
_ADMIN_ROLES = {"admin", "operations_manager", "tenant_admin"}
_ADMIN_OR_FINANCE = {"admin", "operations_manager", "accountant"}
_ADMIN_OR_SUPPORT = {"admin", "operations_manager", "support_agent"}


async def _ws_authorized_subscribe(
    ws: WebSocket,
    channel: str,
    access_token: str | None,
    tenant_id_query: str | None,
    *,
    path_user_id: str | None = None,
    path_tech_id: str | None = None,
    allowed_roles: set[str] | None = None,
) -> None:
    """驗 token + 通道授權 → accept → subscribe → 等待 disconnect → unsubscribe。"""
    try:
        auth = await verify_ws_token(
            access_token=access_token, tenant_id_query=tenant_id_query
        )
        authorize_channel(
            channel=channel,
            auth=auth,
            path_user_id=path_user_id,
            path_tech_id=path_tech_id,
            allowed_roles=allowed_roles,
        )
    except WSAuthError as e:
        await ws.close(code=e.code, reason=e.reason)
        return
    await ws.accept()
    await hub.subscribe(channel, ws)
    try:
        while True:
            await ws.receive_text()  # 單向 push，client→server 訊息忽略
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(channel, ws)


@app.websocket("/realtime/notifications/{user_id}")
async def ws_notifications(
    websocket: WebSocket,
    user_id: str,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    # 任何登入者都可以訂閱自己的通知頻道（user_id 必須等於 token sub）
    await _ws_authorized_subscribe(
        websocket,
        f"/realtime/notifications/{user_id}",
        access_token,
        tenant_id,
        path_user_id=user_id,
    )


@app.websocket("/realtime/work-orders/{wo_id}")
async def ws_work_orders(
    websocket: WebSocket,
    wo_id: str,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    # tenant 內任何登入者都可訂閱該工單事件（後續若需精細 ACL 再擴充）
    await _ws_authorized_subscribe(
        websocket,
        f"/realtime/work-orders/{wo_id}",
        access_token,
        tenant_id,
    )


@app.websocket("/realtime/dispatch-queue")
async def ws_dispatch_queue(
    websocket: WebSocket,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    await _ws_authorized_subscribe(
        websocket,
        "/realtime/dispatch-queue",
        access_token,
        tenant_id,
        allowed_roles=_ADMIN_ROLES,
    )


@app.websocket("/realtime/sla-alerts")
async def ws_sla_alerts(
    websocket: WebSocket,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    await _ws_authorized_subscribe(
        websocket,
        "/realtime/sla-alerts",
        access_token,
        tenant_id,
        allowed_roles=_ADMIN_ROLES,
    )


@app.websocket("/realtime/refunds")
async def ws_refunds(
    websocket: WebSocket,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    await _ws_authorized_subscribe(
        websocket,
        "/realtime/refunds",
        access_token,
        tenant_id,
        allowed_roles=_ADMIN_OR_FINANCE,
    )


@app.websocket("/realtime/disputes")
async def ws_disputes(
    websocket: WebSocket,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    await _ws_authorized_subscribe(
        websocket,
        "/realtime/disputes",
        access_token,
        tenant_id,
        allowed_roles=_ADMIN_OR_SUPPORT,
    )


@app.websocket("/realtime/inventory/low-stock")
async def ws_inventory(
    websocket: WebSocket,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    await _ws_authorized_subscribe(
        websocket,
        "/realtime/inventory/low-stock",
        access_token,
        tenant_id,
        allowed_roles=_ADMIN_ROLES,
    )


@app.websocket("/realtime/rbac")
async def ws_rbac(
    websocket: WebSocket,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    # 任何登入者都應收到 RBAC 變更（觸發頁面 reload 重新拉權限）
    await _ws_authorized_subscribe(
        websocket, "/realtime/rbac", access_token, tenant_id
    )


@app.websocket("/realtime/pool/{tech_id}")
async def ws_pool(
    websocket: WebSocket,
    tech_id: str,
    access_token: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
):
    # 技師訂閱自己的 pool；admin/operations_manager 可訂閱任何技師（監控）
    await _ws_authorized_subscribe(
        websocket,
        f"/realtime/pool/{tech_id}",
        access_token,
        tenant_id,
        path_tech_id=tech_id,
    )
