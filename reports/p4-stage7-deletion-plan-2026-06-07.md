# P4 Stage 7 — v1 Router 刪除計畫 (Dry-Run)

Safe list endpoints: 0
v1 router modules in main.py: 47
v1 router files found: 47

## §1 候選刪除檔案

- `api/routers/admin_schedule.py` (2.6 KB)
- `api/routers/audit_logs.py` (8.6 KB)
- `api/routers/auth.py` (3.3 KB)
- `api/routers/cancellation.py` (2.7 KB)
- `api/routers/config_m18.py` (17.3 KB)
- `api/routers/conversations.py` (4.8 KB)
- `api/routers/customers.py` (4.6 KB)
- `api/routers/dashboard.py` (0.8 KB)
- `api/routers/data_corrections.py` (2.8 KB)
- `api/routers/deprecation_metrics.py` (1.2 KB)
- `api/routers/device_warranty.py` (5.5 KB)
- `api/routers/dispatch.py` (4.8 KB)
- `api/routers/dispatch_logs.py` (1.4 KB)
- `api/routers/disputes.py` (3.4 KB)
- `api/routers/family_reviews.py` (2.5 KB)
- `api/routers/inventory.py` (1.6 KB)
- `api/routers/invoices.py` (1.7 KB)
- `api/routers/kb_cases.py` (4.5 KB)
- `api/routers/kb_export.py` (2.8 KB)
- `api/routers/kb_manuals.py` (2.8 KB)
- `api/routers/lifespan_health.py` (3.6 KB)
- `api/routers/line_webhook.py` (8.5 KB)
- `api/routers/media.py` (2.8 KB)
- `api/routers/notifications.py` (4.0 KB)
- `api/routers/pricing_rules.py` (3.7 KB)
- `api/routers/problem_cards.py` (10.0 KB)
- `api/routers/public.py` (5.0 KB)
- `api/routers/reconciliations.py` (2.4 KB)
- `api/routers/refunds.py` (4.1 KB)
- `api/routers/reports_customer_satisfaction.py` (1.7 KB)
- `api/routers/reports_export.py` (2.8 KB)
- `api/routers/reports_kpi.py` (1.5 KB)
- `api/routers/reports_operational_kpi.py` (1.4 KB)
- `api/routers/resolution.py` (1.1 KB)
- `api/routers/revenue.py` (1.3 KB)
- `api/routers/roles.py` (3.6 KB)
- `api/routers/sentiment_alerts.py` (2.4 KB)
- `api/routers/settlements.py` (1.3 KB)
- `api/routers/sop_drafts.py` (4.5 KB)
- `api/routers/system_config.py` (1.3 KB)
- `api/routers/technicians.py` (8.4 KB)
- `api/routers/v1_inventory.py` (3.8 KB)
- `api/routers/vouchers.py` (2.3 KB)
- `api/routers/vouchers_void.py` (2.8 KB)
- `api/routers/warranty_claims.py` (4.4 KB)
- `api/routers/work_order_actions.py` (3.8 KB)
- `api/routers/work_orders.py` (19.0 KB)

## §2 main.py 需修改的行

### Import 行

- L25: `from routers import auth as auth_router`
- L26: `from routers import notifications as notifications_router`
- L27: `from routers import system_config as system_config_router`
- L28: `from routers import kb_cases as kb_cases_router`
- L29: `from routers import kb_manuals as kb_manuals_router`
- L30: `from routers import sop_drafts as sop_drafts_router`
- L31: `from routers import audit_logs as audit_logs_router`
- L32: `from routers import conversations as conversations_router`
- L33: `from routers import dashboard as dashboard_router`
- L34: `from routers import problem_cards as problem_cards_router`
- L35: `from routers import work_orders as work_orders_router`
- L36: `from routers import work_order_actions as work_order_actions_router`
- L37: `from routers import technicians as technicians_router`
- L38: `from routers import admin_schedule as admin_schedule_router`
- L39: `from routers import media as media_router`
- L40: `from routers import dispatch_logs as dispatch_logs_router`
- L41: `from routers import dispatch as dispatch_router`
- L42: `from routers import settlements as settlements_router`
- L43: `from routers import reconciliations as reconciliations_router`
- L44: `from routers import invoices as invoices_router`
- L45: `from routers import refunds as refunds_router`
- L46: `from routers import warranty_claims as warranty_claims_router`
- L47: `from routers import disputes as disputes_router`
- L48: `from routers import revenue as revenue_router`
- L49: `from routers import pricing_rules as pricing_rules_router`
- L50: `from routers import customers as customers_router`
- L51: `from routers import roles as roles_router`
- L52: `from routers import inventory as inventory_router`
- L53: `from routers import reports_kpi as reports_kpi_router`
- L54: `from routers import reports_export as reports_export_router`
- L55: `from routers import resolution as resolution_router`
- L56: `from routers import kb_export as kb_export_router`
- L57: `from routers import sentiment_alerts as sentiment_alerts_router`
- L58: `from routers import vouchers as vouchers_router`
- L59: `from routers import family_reviews as family_reviews_router`
- L60: `from routers import data_corrections as data_corrections_router`
- L61: `from routers import public as public_router`
- L62: `from routers import cancellation as cancellation_router`
- L64: `from routers import device_warranty as device_warranty_router`
- L90: `from routers import config_m18 as config_m18_router`
- L97: `from routers import vouchers_void as vouchers_void_router`
- L98: `from routers import line_webhook as line_webhook_router`
- L102: `from routers import reports_customer_satisfaction as reports_cs_router`
- L103: `from routers import reports_operational_kpi as reports_okpi_router`
- L114: `from routers import deprecation_metrics as deprecation_metrics_router`
- L115: `from routers import v1_inventory as v1_inventory_router`
- L116: `from routers import lifespan_health as lifespan_health_router`

### Include_router 行

- L186: `app.include_router(auth_router.router, prefix="/api/v1", tags=["auth"])`
- L187: `app.include_router(notifications_router.router, prefix="/api/v1", tags=["realtime"])`
- L188: `app.include_router(system_config_router.router, prefix="/api/v1", tags=["user_management"])`
- L189: `app.include_router(kb_cases_router.router, prefix="/api/v1", tags=["knowledge_base"])`
- L190: `app.include_router(kb_manuals_router.router, prefix="/api/v1", tags=["knowledge_base"])`
- L191: `app.include_router(sop_drafts_router.router, prefix="/api/v1", tags=["knowledge_base"])`
- L192: `app.include_router(family_reviews_router.router, prefix="/api/v1", tags=["knowledge_base"])`
- L193: `app.include_router(audit_logs_router.router, prefix="/api/v1", tags=["observability"])`
- L194: `app.include_router(data_corrections_router.router, prefix="/api/v1", tags=["knowledge_base"])`
- L195: `app.include_router(conversations_router.router, prefix="/api/v1", tags=["customer_service"])`
- L196: `app.include_router(sentiment_alerts_router.router, prefix="/api/v1", tags=["customer_service"])`
- L197: `app.include_router(dashboard_router.router, prefix="/api/v1", tags=["reports"])`
- L198: `app.include_router(problem_cards_router.router, prefix="/api/v1", tags=["customer_service"])`
- L199: `app.include_router(work_orders_router.router, prefix="/api/v1", tags=["dispatch"])`
- L200: `app.include_router(work_order_actions_router.router, prefix="/api/v1", tags=["dispatch"])`
- L201: `app.include_router(technicians_router.router, prefix="/api/v1", tags=["dispatch"])`
- L202: `app.include_router(admin_schedule_router.router, prefix="/api/v1", tags=["dispatch"])`
- L203: `app.include_router(media_router.router, prefix="/api/v1", tags=["media"])`
- L204: `app.include_router(dispatch_logs_router.router, prefix="/api/v1", tags=["dispatch"])`
- L205: `app.include_router(dispatch_router.router, prefix="/api/v1", tags=["dispatch"])`
- L206: `app.include_router(settlements_router.router, prefix="/api/v1", tags=["accounting"])`
- L207: `app.include_router(vouchers_router.router, prefix="/api/v1", tags=["accounting"])`
- L208: `app.include_router(reconciliations_router.router, prefix="/api/v1", tags=["accounting"])`
- L209: `app.include_router(invoices_router.router, prefix="/api/v1", tags=["accounting"])`
- L210: `app.include_router(refunds_router.router, prefix="/api/v1", tags=["accounting"])`
- L211: `app.include_router(warranty_claims_router.router, prefix="/api/v1", tags=["accounting"])`
- L212: `app.include_router(disputes_router.router, prefix="/api/v1", tags=["accounting"])`
- L213: `app.include_router(revenue_router.router, prefix="/api/v1", tags=["reports"])`
- L214: `app.include_router(pricing_rules_router.router, prefix="/api/v1", tags=["accounting"])`
- L215: `app.include_router(customers_router.router, prefix="/api/v1", tags=["customer_service"])`
- L216: `app.include_router(roles_router.router, prefix="/api/v1", tags=["user_management"])`
- L217: `app.include_router(inventory_router.router, prefix="/api/v1", tags=["inventory"])`
- L218: `app.include_router(reports_kpi_router.router, prefix="/api/v1", tags=["reports"])`
- L219: `app.include_router(reports_export_router.router, prefix="/api/v1", tags=["reports"])`
- L220: `app.include_router(resolution_router.router, prefix="/api/v1", tags=["customer_service"])`
- L221: `app.include_router(kb_export_router.router, prefix="/api/v1", tags=["knowledge_base"])`
- L224: `app.include_router(public_router.router, prefix="/api/v1", tags=["public"])`
- L226: `app.include_router(cancellation_router.router, tags=["M11 AR / Payment"])`
- L228: `app.include_router(refunds_v2_router.router, tags=["M11 AR / Payment"])`
- L230: `app.include_router(device_warranty_router.router, tags=["M13 Warranty"])`
- L231: `app.include_router(customers_v2_router.router, tags=["M04 Customer"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)`
- L232: `app.include_router(rbac_v2_router.router, tags=["M17 RBAC"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)`
- L235: `app.include_router(vouchers_v2_router.router, tags=["M17 Voucher"])  # spec-alignment P2-α (CR-0002-α, M17 Voucher tenant-scoped)`
- L236: `app.include_router(audit_v2_router.router, tags=["M17 Audit"])  # spec-alignment P2-α (CR-0002-α)`
- L237: `app.include_router(problem_cards_v2_router.router, tags=["M03 ProblemCard"])  # spec-alignment P2-α (CR-0002-α, M03 ProblemCard tenant-scoped)`
- L238: `app.include_router(tech_lifecycle_v2_router.router, tags=["M07 Technician Lifecycle"])  # 必須先於 technicians_v2_router (lifecycle-events literal segment vs {techId} catch-all)`
- L239: `app.include_router(technicians_v2_router.router, tags=["M05 Technician"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)`
- L240: `app.include_router(dispatch_v2_router.router, tags=["M06 Dispatch"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)`
- L243: `app.include_router(work_orders_ops_v2_router.router, tags=["M07 WorkOrder Ops"])  # spec-alignment P2-W4 (route-order before /{woId})`
- L244: `app.include_router(work_orders_v2_router.router, tags=["M06 WorkOrder"])  # spec-alignment P2-α (CR-0002-α, tenant-scoped)`
- L245: `app.include_router(pricing_v2_router.router, tags=["M11 Pricing"])  # spec-alignment P2-α (CR-0002-α, M11 Pricing calculate tenant-scoped)`
- L246: `app.include_router(consumer_v2_router.router, tags=["M16 Consumer"])  # spec-alignment P2-α (CR-0002-α, M16 Consumer public token)`
- L247: `app.include_router(settlements_v2_router.router, tags=["M12 Settlement"])  # spec-alignment P2 (FR-0012, M12 monthly settlement 501 stub)`
- L248: `app.include_router(warranty_claims_v2_router.router, tags=["M13 Warranty"])  # spec-alignment P2 (CR-0003 P2, M13 Warranty POST create tenant-scoped)`
- L249: `app.include_router(exceptions_v2_router.router, tags=["M15 Exception"])  # spec-alignment P2 (CR-0003, M15 Exception tenant-scoped)`
- L250: `app.include_router(dashboard_v2_router.router, tags=["Dashboard"])  # spec-alignment P2-W1 (CR-0003 P2-W1, Dashboard tenant-scoped, FR-0021)`
- L251: `app.include_router(reports_v2_router.router, tags=["Reports"])  # spec-alignment P2-W1 (CR-0003 P2-W1, FR-0021, Reports kpi/revenue/export tenant-scoped)`
- L252: `app.include_router(sentiment_alerts_v2_router.router, tags=["Sentiment Alerts"])  # spec-alignment P2-W2 (CR-0003 P2-W2, FR-0018/ADR-0048, Sentiment Alerts tenant-scoped)`
- L253: `app.include_router(notifications_v2_router.router, tags=["Notifications"])  # spec-alignment P2-W2 (CR-0003 P2-W2, ADR-0012, Notifications tenant-scoped)`
- L254: `app.include_router(conversations_v2_router.router, tags=["Conversations"])  # spec-alignment P2-W2 (CR-0003 P2-W2, FR-0018, Conversations tenant-scoped)`
- L255: `app.include_router(sops_v2_router.router, tags=["SOP Review"])  # spec-alignment P2-W3 (CR-0003 P2-W3, SOP Review dual+family flat-path)`
- L256: `app.include_router(kb_v2_router.router, tags=["KB (Agent Knowledge Base)"])  # spec-alignment P2-W3 (CR-0003 P2-W3, KB documents v2, ADR-0101)`
- L257: `app.include_router(invoices_v2_router.router, tags=["M11 Invoice"])  # spec-alignment P2-W5 (CR-0003 P2-W5, M11 Invoice read-only tenant-scoped, FR-0011)`
- L258: `app.include_router(media_v2_router.router, tags=["Media"])  # spec-alignment P2-W6 (CR-0003 P2-W6, Media tenant-scoped upload/serve/list)`
- L259: `app.include_router(dispatch_logs_v2_router.router, tags=["M06 Dispatch"])  # spec-alignment P2-W6 (BUILD_TENANT_SCOPED, M06 DispatchLogs read-only tenant-scoped, admin-only)`
- L260: `app.include_router(config_m18_router.router, tags=["M18 Config Governance"])  # Track B S1: M18 Runtime Config Governance (ADR-0067 Phase 0 / CR-0004 §8)`
- L261: `app.include_router(reconciliations_v2_router.router, tags=["M12 Reconciliation"])  # Track B S2: Reconciliation dual-sign (FR-0013 / CR-0004 §8)`
- L262: `app.include_router(disputes_v2_router.router, tags=["M14 Dispute"])  # Track B S2: Dispute dual-sign 狀態機 (FR-0013 / CR-0004 §8)`
- L263: `app.include_router(inventory_v2_router.router, tags=["M10 Inventory"])  # Track B S3: Inventory v2 per-tenant 庫存狀態機 (FR-0007 / CR-0004 §8)`
- L264: `app.include_router(pricing_rules_v2_router.router, tags=["M11 Pricing Rules"])  # Track B S4: Pricing Rules v2 tenant-scoped CRUD + change_request 審計 (CR-0004 §8 C3 / ADR-0046)`
- L265: `app.include_router(data_corrections_v2_router.router, tags=["M09 Data Corrections"])  # Track B S5: DataCorrections v2 tenant-scoped review queue (CR-0004 §8 / ADR-0029 / ADR-0030)`
- L266: `app.include_router(resolution_v2_router.router, tags=["M03 ProblemCard"])  # Track B S6: Resolution engine v2 tenant-scoped suggest (CR-0004 §8 C4)`
- L267: `app.include_router(vouchers_void_router.router, tags=["M17 Voucher"])  # Track B S7: Voucher Void v2 紅字沖銷 flat path (ADR-VCH-001/002 / CR-0004 §8)`
- L268: `app.include_router(line_webhook_router.router, prefix="/api/v1", tags=["LINE Webhook"])  # CR-0017 Stage 4: LINE postback handler`
- L269: `app.include_router(recon_exceptions_v2_router.router, tags=["M12 Reconciliation Exception"])  # CR-0018 Stage 2: Flow 13 EX5 reconciliation_exception 7 endpoints`
- L270: `app.include_router(monthly_settlements_v2_router.router, tags=["M12 Monthly Settlement"])  # CR-0012 Stage 2: Manual CSV 月結 5 endpoints (HD-1 V1)`
- L271: `app.include_router(sop_performance_v2_router.router, tags=["M14 SOP Performance"])  # WBS §8 P1: SOP 績效真實化`
- L272: `app.include_router(reports_cs_router.router, prefix="/api/v1", tags=["Reports"])  # WBS §8 P2: 客戶滿意度 KPI`
- L273: `app.include_router(reports_okpi_router.router, prefix="/api/v1", tags=["Reports"])  # WBS §8 P2: FTFR + SLA on-time KPI`
- L274: `app.include_router(approval_inbox_v2_router.router, tags=["M15 Approval Inbox"])  # FR-0049 MVP: Exception Approval Inbox`
- L275: `app.include_router(scheduled_reports_v2_router.router, tags=["Reports"])  # Admin 報表排程`
- L277: `app.include_router(gdpr_forget_v2_router.router, tags=["M17 GDPR Forget"])  # FR-0053 MVP: GDPR Right-to-be-Forgotten`
- L278: `app.include_router(ai_gov_v2_router.router, tags=["A12 AI Governance"])  # FR-0050 MVP: AI Governance Trace Store`
- L279: `app.include_router(sop_feedback_v2_router.router, tags=["A10 SOP Feedback"])  # FR-0051 MVP: SOP Feedback Spiral`
- L280: `app.include_router(rma_quality_v2_router.router, tags=["M13 RMA Quality"])  # FR-0048 MVP: RMA Quality Feedback Loop`
- L281: `app.include_router(tech_statement_v2_router.router, tags=["M12 Tech AP Statement"])  # FR-0045 MVP: Technician AP Statement`
- L282: `app.include_router(disp_comm_v2_router.router, tags=["M12 Dispatcher Commission"])  # FR-0046 MVP: Dispatcher Commission`
- L283: `app.include_router(brand_b2b_v2_router.router, tags=["M12 Brand B2B Settlement"])  # FR-0047 MVP: Brand B2B Settlement`
- L284: `app.include_router(deprecation_metrics_router.router, prefix="/api/v1", tags=["Admin Deprecation Metrics"])  # P4 Cutover 規劃`
- L285: `app.include_router(v1_inventory_router.router, prefix="/api/v1", tags=["Admin V1 Inventory"])  # P4 Cutover 規劃`
- L286: `app.include_router(lifespan_health_router.router, prefix="/api/v1", tags=["Admin Lifespan Health"])  # 8 monitor 健康查詢`

## §3 業主簽核對應 safe list

⚠️ 未提供 safe list — 不可執行真實刪除

## §4 後續真實刪除 PR 步驟（非本 script）

1. 開 branch `chore/p4-stage7-delete-v1-routers`
2. 依 §1 刪除 router 檔案
3. 依 §2 移除 main.py import + include_router 行
4. 刪除 router 對應 test 檔案 (`api/tests/test_*_v1.py` 等)
5. 更新 `docs/architecture/api/openapi.yaml` 移除 v1 path
6. 跑 `.venv/bin/pytest api/tests/` 確認無 regression
7. 跑 `scripts/ops/smoke_test_production.py` 確認 v2 全綠
8. 開 PR + reference ADR (新立 ADR 記錄 Stage 7 完成)
9. Merge 後 push, ops 觀察 24h

## §5 Risk Mitigation

- ❗ **若 safe list 與 router files 不對應**: 不可執行刪除
  → 業主重簽 / 重跑 aggregate report
- ❗ **若 main.py import 在 §3 之外仍被引用**: dead code, 刪後
  Python import error → run 完整 pytest 抓
- ❗ **若 v1 router 與 v2 共用 service**: 安全 (service 不刪)
- ❗ **若 v1 router 有獨有 helper**: 移到對應 v2 router 或共用 lib