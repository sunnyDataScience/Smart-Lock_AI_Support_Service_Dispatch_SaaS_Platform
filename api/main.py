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
from middleware.deprecation import DeprecationMiddleware  # CR-0002-α D3：legacy /api/v1 全標 Deprecation
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
from routers import refunds_v2 as refunds_v2_router  # spec-alignment P1-B (ADR-0040v2, tenant-scoped SoD+5tier)
from routers import device_warranty as device_warranty_router  # spec-alignment P1-B (ADR-0044 v2, tenant-scoped)
from routers import customers_v2 as customers_v2_router  # spec-alignment P2-α (CR-0002-α, tenant-scoped M04 Customer)
from routers import rbac_v2 as rbac_v2_router  # spec-alignment P2-α (CR-0002-α, M17 RBAC tenant-scoped)
# ⬇ APPEND-ANCHOR（spec-alignment 平行波次）：新 tenant-scoped v2 router import 在此一行一個 append（P2/P3）
from routers import vouchers_v2 as vouchers_v2_router  # spec-alignment P2-α (CR-0002-α, M17 Voucher tenant-scoped)
from routers import audit_v2 as audit_v2_router  # spec-alignment P2-α (CR-0002-α, M17 audit tenant-scoped)
from routers import problem_cards_v2 as problem_cards_v2_router  # spec-alignment P2-α (CR-0002-α, M03 ProblemCard tenant-scoped)
from routers import technicians_v2 as technicians_v2_router  # spec-alignment P2-α (CR-0002-α, M05 Technician tenant-scoped)
from routers import dispatch_v2 as dispatch_v2_router  # spec-alignment P2-α (CR-0002-α, M06 Dispatch tenant-scoped)
from routers import work_orders_v2 as work_orders_v2_router  # spec-alignment P2-α (CR-0002-α, M06 WorkOrder tenant-scoped)
from routers import pricing_v2 as pricing_v2_router  # spec-alignment P2-α (CR-0002-α, M11 Pricing calculate tenant-scoped)
from routers import consumer_v2 as consumer_v2_router  # spec-alignment P2-α (CR-0002-α, M16 Consumer public token)
from routers import settlements_v2 as settlements_v2_router  # spec-alignment P2 (FR-0012, M12 Settlement monthly trigger 501 stub)
from routers import warranty_claims_v2 as warranty_claims_v2_router  # spec-alignment P2 (CR-0003 P2, M13 Warranty POST create tenant-scoped)
from routers import exceptions_v2 as exceptions_v2_router  # spec-alignment P2 (CR-0003, M15 Exception tenant-scoped)
from routers import dashboard_v2 as dashboard_v2_router  # spec-alignment P2-W1 (CR-0003 P2-W1, Dashboard tenant-scoped, FR-0021)
from routers import reports_v2 as reports_v2_router  # spec-alignment P2-W1 (CR-0003 P2-W1, FR-0021, Reports tenant-scoped)
from routers import sentiment_alerts_v2 as sentiment_alerts_v2_router  # spec-alignment P2-W2 (CR-0003 P2-W2, Sentiment Alerts tenant-scoped, FR-0018/ADR-0048)
from routers import notifications_v2 as notifications_v2_router  # spec-alignment P2-W2 (CR-0003 P2-W2, ADR-0012, Notifications tenant-scoped)
from routers import conversations_v2 as conversations_v2_router  # spec-alignment P2-W2 (CR-0003 P2-W2, FR-0018, Conversations tenant-scoped)
from routers import sops_v2 as sops_v2_router  # spec-alignment P2-W3 (CR-0003 P2-W3, SOP Review dual+family flat-path)
from routers import kb_v2 as kb_v2_router  # spec-alignment P2-W3 (CR-0003 P2-W3, KB documents v2, ADR-0101)
from routers import work_orders_ops_v2 as work_orders_ops_v2_router  # spec-alignment P2-W4 (CR-0003 P2-W4, M07 WorkOrder Ops tenant-scoped)
from routers import invoices_v2 as invoices_v2_router  # spec-alignment P2-W5 (CR-0003 P2-W5, M11 Invoice read-only tenant-scoped, FR-0011)
from routers import media_v2 as media_v2_router  # spec-alignment P2-W6 (CR-0003 P2-W6, Media tenant-scoped upload/serve/list)
from routers import dispatch_logs_v2 as dispatch_logs_v2_router  # spec-alignment P2-W6 (BUILD_TENANT_SCOPED, M06 DispatchLogs read-only tenant-scoped, admin-only)
from routers import config_m18 as config_m18_router  # Track B S1: M18 Runtime Config Governance (ADR-0067 Phase 0 / CR-0004 §8)
from routers import reconciliations_v2 as reconciliations_v2_router  # Track B S2: Reconciliation dual-sign (FR-0013 / CR-0004 §8 HD-1~HD-3)
from routers import disputes_v2 as disputes_v2_router  # Track B S2: Dispute dual-sign 狀態機 (FR-0013 / CR-0004 §8 HD-1~HD-4)
from routers import inventory_v2 as inventory_v2_router  # Track B S3: Inventory v2 per-tenant 庫存狀態機 (FR-0007 / CR-0004 §8 / ADR-0052 / ADR-0053)
from routers import pricing_rules_v2 as pricing_rules_v2_router  # Track B S4: Pricing Rules v2 tenant-scoped CRUD + change_request 審計 (CR-0004 §8 C3 / ADR-0046)
from routers import data_corrections_v2 as data_corrections_v2_router  # Track B S5: DataCorrections v2 tenant-scoped review queue + resolved 第四態 + require_admin (CR-0004 §8 / ADR-0029 / ADR-0030)
from routers import resolution_v2 as resolution_v2_router  # Track B S6: Resolution engine v2 tenant-scoped suggest (CR-0004 §8 C4)
from routers import vouchers_void as vouchers_void_router  # Track B S7: Voucher Void v2 紅字沖銷 flat path (ADR-VCH-001/002 / CR-0004 §8)
from routers import line_webhook as line_webhook_router  # CR-0017 Stage 4: LINE postback → reschedule/scope_change wrapper
from routers import reconciliation_exceptions_v2 as recon_exceptions_v2_router  # CR-0018 Stage 2: Flow 13 EX5 對帳異常 dual-sign + 3 fix_path
from routers import monthly_settlements_v2 as monthly_settlements_v2_router  # CR-0012 Stage 2: Manual CSV 月結撥款
from routers import sop_performance_v2 as sop_performance_v2_router  # WBS §8 P1: SOP 績效真實化 metrics
from routers import reports_customer_satisfaction as reports_cs_router  # WBS §8 P2: 客戶滿意度 KPI 擴充
from routers import reports_operational_kpi as reports_okpi_router  # WBS §8 P2: FTFR + SLA on-time KPI
from routers import approval_inbox_v2 as approval_inbox_v2_router  # FR-0049 MVP: Exception Approval Inbox
from routers import scheduled_reports_v2 as scheduled_reports_v2_router  # 報表排程 (migration 029)
from routers import technician_lifecycle_v2 as tech_lifecycle_v2_router  # FR-0044 MVP: Technician Lifecycle
from routers import gdpr_forget_v2 as gdpr_forget_v2_router  # FR-0053 MVP: GDPR Right-to-be-Forgotten
from routers import ai_governance_trace_v2 as ai_gov_v2_router  # FR-0050 MVP: AI Governance Trace
from routers import sop_feedback_v2 as sop_feedback_v2_router  # FR-0051 MVP: SOP Feedback Spiral
from routers import rma_quality_v2 as rma_quality_v2_router  # FR-0048 MVP: RMA Quality Feedback Loop
from routers import technician_statement_v2 as tech_statement_v2_router  # FR-0045 MVP: Technician AP Statement
from routers import dispatcher_commission_v2 as disp_comm_v2_router  # FR-0046 MVP: Dispatcher Commission
from routers import brand_b2b_statement_v2 as brand_b2b_v2_router  # FR-0047 MVP: Brand B2B Settlement
from routers import deprecation_metrics as deprecation_metrics_router  # P4 Cutover 規劃: v1 hit metrics
from routers import v1_inventory as v1_inventory_router  # P4 Cutover 規劃: v1 routers inventory
from routers import lifespan_health as lifespan_health_router  # admin 查 8 monitor 健康

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

cfg = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: 連線 DB → 啟動 monitors → 關閉。"""
    await init_db(cfg.database)
    # 啟動背景監測（單機 in-memory；多 worker 須改 distributed scheduler）
    from realtime.config_canary_advance_cron import worker as canary_advance_cron
    from realtime.dispute_escalation_cron import worker as dispute_escalation_cron
    from realtime.inventory_monitor import monitor as inventory_monitor
    from realtime.line_push_outbox_worker import worker as line_push_worker
    from realtime.reconciliation_exception_detector import worker as recon_exc_detector
    from realtime.gdpr_hard_delete_cron import worker as gdpr_hard_delete
    from realtime.sla_monitor import monitor as sla_monitor
    from realtime.statement_auto_approval_cron import worker as statement_auto_approval

    inventory_monitor.start()
    sla_monitor.start()
    line_push_worker.start()  # CR-0017 Stage 2 outbox poll → push LINE
    recon_exc_detector.start()  # CR-0018 Stage 3 cron daily 對帳異常偵測
    dispute_escalation_cron.start()  # WBS §8 P1: 60d dispute 自動 escalation
    canary_advance_cron.start()  # WBS §8 P1: M18 canary 5%→50%→100% 自動推進
    statement_auto_approval.start()  # Phase II: 3 statement 表 dispute window 過期 auto-approve
    gdpr_hard_delete.start()  # FR-0053: T+30 GDPR forget 自動硬刪
    logger.info("API service ready (port=%s)", cfg.system["port"])
    yield
    await gdpr_hard_delete.stop()
    await statement_auto_approval.stop()
    await canary_advance_cron.stop()
    await dispute_escalation_cron.stop()
    await recon_exc_detector.stop()
    await line_push_worker.stop()
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
app.add_middleware(DeprecationMiddleware)  # CR-0002-α D3：/api/v1/* 回應一律 Deprecation: true（含 error path）

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
# spec-alignment P1-B：tenant-scoped 退款端點（三維 SoD + 5-tier），無 /api/v1 前綴對齊 spec
app.include_router(refunds_v2_router.router, tags=["M11 AR / Payment"])
# spec-alignment P1-B：tenant-scoped 保固端點（5-mode），無 /api/v1 前綴以對齊 frozen spec path
app.include_router(device_warranty_router.router, tags=["M13 Warranty"])
app.include_router(customers_v2_router.router, tags=["M04 Customer"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)
app.include_router(rbac_v2_router.router, tags=["M17 RBAC"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)
# ⬇ APPEND-ANCHOR（spec-alignment 平行波次）：新 tenant-scoped v2 router include 在此一行一個 append（P2/P3）
#   注意：FastAPI 漏 include_router 不報錯 → silent 404，新增務必同時補 import-anchor 與此處。
app.include_router(vouchers_v2_router.router, tags=["M17 Voucher"])  # spec-alignment P2-α (CR-0002-α, M17 Voucher tenant-scoped)
app.include_router(audit_v2_router.router, tags=["M17 Audit"])  # spec-alignment P2-α (CR-0002-α)
app.include_router(problem_cards_v2_router.router, tags=["M03 ProblemCard"])  # spec-alignment P2-α (CR-0002-α, M03 ProblemCard tenant-scoped)
app.include_router(technicians_v2_router.router, tags=["M05 Technician"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)
app.include_router(dispatch_v2_router.router, tags=["M06 Dispatch"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)
# work_orders_ops_v2 須先於 work_orders_v2 註冊：/work-orders/pool、/dispatch/queue 為 literal 段，
# 否則被 work_orders_v2 的 /work-orders/{woId} param 路由吃掉（"pool" → uuid 解析失敗）。
app.include_router(work_orders_ops_v2_router.router, tags=["M07 WorkOrder Ops"])  # spec-alignment P2-W4 (route-order before /{woId})
app.include_router(work_orders_v2_router.router, tags=["M06 WorkOrder"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)
app.include_router(pricing_v2_router.router, tags=["M11 Pricing"])  # spec-alignment P2-α (CR-0002-α, M11 Pricing calculate tenant-scoped)
app.include_router(consumer_v2_router.router, tags=["M16 Consumer"])  # spec-alignment P2-α (CR-0002-α, M16 Consumer public token)
app.include_router(settlements_v2_router.router, tags=["M12 Settlement"])  # spec-alignment P2 (FR-0012, M12 monthly settlement 501 stub)
app.include_router(warranty_claims_v2_router.router, tags=["M13 Warranty"])  # spec-alignment P2 (CR-0003 P2, M13 Warranty POST create tenant-scoped)
app.include_router(exceptions_v2_router.router, tags=["M15 Exception"])  # spec-alignment P2 (CR-0003, M15 Exception tenant-scoped)
app.include_router(dashboard_v2_router.router, tags=["Dashboard"])  # spec-alignment P2-W1 (CR-0003 P2-W1, Dashboard tenant-scoped, FR-0021)
app.include_router(reports_v2_router.router, tags=["Reports"])  # spec-alignment P2-W1 (CR-0003 P2-W1, FR-0021, Reports kpi/revenue/export tenant-scoped)
app.include_router(sentiment_alerts_v2_router.router, tags=["Sentiment Alerts"])  # spec-alignment P2-W2 (CR-0003 P2-W2, FR-0018/ADR-0048, Sentiment Alerts tenant-scoped)
app.include_router(notifications_v2_router.router, tags=["Notifications"])  # spec-alignment P2-W2 (CR-0003 P2-W2, ADR-0012, Notifications tenant-scoped)
app.include_router(conversations_v2_router.router, tags=["Conversations"])  # spec-alignment P2-W2 (CR-0003 P2-W2, FR-0018, Conversations tenant-scoped)
app.include_router(sops_v2_router.router, tags=["SOP Review"])  # spec-alignment P2-W3 (CR-0003 P2-W3, SOP Review dual+family flat-path)
app.include_router(kb_v2_router.router, tags=["KB (Agent Knowledge Base)"])  # spec-alignment P2-W3 (CR-0003 P2-W3, KB documents v2, ADR-0101)
app.include_router(invoices_v2_router.router, tags=["M11 Invoice"])  # spec-alignment P2-W5 (CR-0003 P2-W5, M11 Invoice read-only tenant-scoped, FR-0011)
app.include_router(media_v2_router.router, tags=["Media"])  # spec-alignment P2-W6 (CR-0003 P2-W6, Media tenant-scoped upload/serve/list)
app.include_router(dispatch_logs_v2_router.router, tags=["M06 Dispatch"])  # spec-alignment P2-W6 (BUILD_TENANT_SCOPED, M06 DispatchLogs read-only tenant-scoped, admin-only)
app.include_router(config_m18_router.router, tags=["M18 Config Governance"])  # Track B S1: M18 Runtime Config Governance (ADR-0067 Phase 0 / CR-0004 §8)
app.include_router(reconciliations_v2_router.router, tags=["M12 Reconciliation"])  # Track B S2: Reconciliation dual-sign (FR-0013 / CR-0004 §8)
app.include_router(disputes_v2_router.router, tags=["M14 Dispute"])  # Track B S2: Dispute dual-sign 狀態機 (FR-0013 / CR-0004 §8)
app.include_router(inventory_v2_router.router, tags=["M10 Inventory"])  # Track B S3: Inventory v2 per-tenant 庫存狀態機 (FR-0007 / CR-0004 §8)
app.include_router(pricing_rules_v2_router.router, tags=["M11 Pricing Rules"])  # Track B S4: Pricing Rules v2 tenant-scoped CRUD + change_request 審計 (CR-0004 §8 C3 / ADR-0046)
app.include_router(data_corrections_v2_router.router, tags=["M09 Data Corrections"])  # Track B S5: DataCorrections v2 tenant-scoped review queue (CR-0004 §8 / ADR-0029 / ADR-0030)
app.include_router(resolution_v2_router.router, tags=["M03 ProblemCard"])  # Track B S6: Resolution engine v2 tenant-scoped suggest (CR-0004 §8 C4)
app.include_router(vouchers_void_router.router, tags=["M17 Voucher"])  # Track B S7: Voucher Void v2 紅字沖銷 flat path (ADR-VCH-001/002 / CR-0004 §8)
app.include_router(line_webhook_router.router, prefix="/api/v1", tags=["LINE Webhook"])  # CR-0017 Stage 4: LINE postback handler
app.include_router(recon_exceptions_v2_router.router, tags=["M12 Reconciliation Exception"])  # CR-0018 Stage 2: Flow 13 EX5 reconciliation_exception 7 endpoints
app.include_router(monthly_settlements_v2_router.router, tags=["M12 Monthly Settlement"])  # CR-0012 Stage 2: Manual CSV 月結 5 endpoints (HD-1 V1)
app.include_router(sop_performance_v2_router.router, tags=["M14 SOP Performance"])  # WBS §8 P1: SOP 績效真實化
app.include_router(reports_cs_router.router, prefix="/api/v1", tags=["Reports"])  # WBS §8 P2: 客戶滿意度 KPI
app.include_router(reports_okpi_router.router, prefix="/api/v1", tags=["Reports"])  # WBS §8 P2: FTFR + SLA on-time KPI
app.include_router(approval_inbox_v2_router.router, tags=["M15 Approval Inbox"])  # FR-0049 MVP: Exception Approval Inbox
app.include_router(scheduled_reports_v2_router.router, tags=["Reports"])  # Admin 報表排程
app.include_router(tech_lifecycle_v2_router.router, tags=["M07 Technician Lifecycle"])  # FR-0044 MVP: Technician Lifecycle
app.include_router(gdpr_forget_v2_router.router, tags=["M17 GDPR Forget"])  # FR-0053 MVP: GDPR Right-to-be-Forgotten
app.include_router(ai_gov_v2_router.router, tags=["A12 AI Governance"])  # FR-0050 MVP: AI Governance Trace Store
app.include_router(sop_feedback_v2_router.router, tags=["A10 SOP Feedback"])  # FR-0051 MVP: SOP Feedback Spiral
app.include_router(rma_quality_v2_router.router, tags=["M13 RMA Quality"])  # FR-0048 MVP: RMA Quality Feedback Loop
app.include_router(tech_statement_v2_router.router, tags=["M12 Tech AP Statement"])  # FR-0045 MVP: Technician AP Statement
app.include_router(disp_comm_v2_router.router, tags=["M12 Dispatcher Commission"])  # FR-0046 MVP: Dispatcher Commission
app.include_router(brand_b2b_v2_router.router, tags=["M12 Brand B2B Settlement"])  # FR-0047 MVP: Brand B2B Settlement
app.include_router(deprecation_metrics_router.router, prefix="/api/v1", tags=["Admin Deprecation Metrics"])  # P4 Cutover 規劃
app.include_router(v1_inventory_router.router, prefix="/api/v1", tags=["Admin V1 Inventory"])  # P4 Cutover 規劃
app.include_router(lifespan_health_router.router, prefix="/api/v1", tags=["Admin Lifespan Health"])  # 8 monitor 健康查詢


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
