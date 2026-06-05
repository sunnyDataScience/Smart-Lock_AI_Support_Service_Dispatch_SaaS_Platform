---
id: OPS-RELEASE-CHECKLIST-2026-06-05
title: Release Checklist — 2026-06-05 session 累積 deploy 清單
status: active
created_at: 2026-06-05
purpose: 把本 session 累積成果（11 migrations / 6 cron / 多 endpoint / Phase II 9 FR MVP）部署到 staging / production 的完整 checklist。
---

# Release Checklist — 2026-06-05

> 部署本 session 累積到 dev_new_arch 的成果到 staging / prod 用。
> 對齊 system-completion-status.md WBS 98% 狀態。

## §1 Pre-Flight

- [ ] dev_new_arch 已 push（HEAD ≥ `8d0b83df`）
- [ ] CI 全綠（342 tests passing in 1.05s）
- [ ] PR/CR 已 review（如有）
- [ ] Staging 部署窗口確認（避業務尖峰）

## §2 SQL Migrations 套用順序

本 session 新增 11 migration (017-027)；按順序套用：

```bash
# 1. 對 staging DB 跑 migrations:
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/017-reconciliation-exceptions.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/018-line-bindings.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/019-monthly-settlement.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/020-tech-lifecycle.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/021-gdpr-forget-requests.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/022-ai-decision-trace.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/023-sop-feedback.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/024-rma-quality-feedback.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/025-tech-ap-statements.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/026-dispatcher-commission.sql
docker exec lock_AI psql -U lock -d lock_AI_data -f SQL/migrations/027-brand-b2b-statements.sql
```

每個 migration 都用 `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` — **冪等可重跑**。

部署完 staging 後在 MIGRATION_REGISTRY.md 把對應 row 從 `🟡 pending-apply` 改 `✅ done`。

## §3 環境變數（新增 / 可調）

| Env | 預設 | 用途 | Required for prod? |
|:---|:---|:---|:---:|
| `LINE_CHANNEL_ACCESS_TOKEN` | — | LINE Flex push (CR-0017) | ✅ |
| `LINE_CHANNEL_SECRET` | — | LINE webhook signature 驗證 | ✅ |
| `LINE_DEFAULT_TENANT_ID` | default tenant | rich menu postback fallback | 建議 |
| `WEB_BASE_URL` | `https://lock-ai-web.example.com` | LINE Flex URI button + GDPR / binding link | ✅ |
| `LINE_PUSH_WORKER_INTERVAL` | 10s | outbox poll cadence | optional |
| `LINE_PUSH_WORKER_BATCH` | 20 | outbox batch size | optional |
| `RECON_EXCEPTION_DETECTOR_INTERVAL` | 86400s (24h) | 對帳異常掃描 | optional |
| `DISPUTE_ESCALATION_CRON_INTERVAL` | 86400s | 60d dispute escalation | optional |
| `CONFIG_CANARY_ADVANCE_INTERVAL` | 300s (5min) | M18 canary advance 掃描 | optional |
| `STATEMENT_AUTO_APPROVAL_INTERVAL` | 3600s (1hr) | 3 statement 表 auto-approve | optional |
| `GDPR_HARD_DELETE_INTERVAL` | 86400s (24h) | T+30 GDPR hard delete | optional |
| `GDPR_HARD_DELETE_BATCH` | 50 | hard delete batch size | optional |
| `SLA_DISPATCH_DELAY_MINUTES` | 30 | FTFR/SLA on-time KPI threshold（已有 sla_monitor 共用） | optional |
| `SLA_ARRIVAL_OVERDUE_MINUTES` | 120 | 同上 | optional |
| `LOADTEST_TECH_TOKENS` | — | CR-0019 Locust 預 seed token CSV（loadtest 用，prod 不需） | ❌ |

## §4 Deploy steps

### 4.1 Staging

- [ ] `./scripts/deploy/api.sh` (Cloud Run pre-flight → build → push → deploy → health check)
- [ ] 跑 §2 migrations
- [ ] 驗 `GET /api/v1/admin/lifespan-monitors/health` `summary.all_running=true`
- [ ] 驗 `GET /api/v1/admin/v1-inventory` 端點正常回應
- [ ] LINE Channel 跑 `scripts/line/setup_rich_menu.py`（首次或更新時）
- [ ] 跑 e2e smoke

### 4.2 Production

- [ ] Staging 連 7 天無 incident
- [ ] Prod ops 部署窗口確認
- [ ] 同 4.1 完整 sequence
- [ ] PagerDuty / Slack alert 接 `monitors-health.yml` workflow
- [ ] 觀察 24 hr 確認 8 monitor 全 `running`

## §5 New Endpoints 速查（部署後驗）

| Tag | Endpoint count | Example |
|:---|:---:|:---|
| LINE Webhook | 1 | `POST /api/v1/line/webhook` |
| M12 Reconciliation Exception | 8 | `POST /tenants/{id}/accounting/reconciliation-exceptions:detect` |
| M12 Monthly Settlement | 5 | `POST :generate / GET csv` |
| M12 Tech AP Statement | 8 | FR-0045 |
| M12 Dispatcher Commission | 8 | FR-0046 |
| M12 Brand B2B Settlement | 8 | FR-0047 |
| M07 Technician Lifecycle | 6 | FR-0044 |
| M17 GDPR Forget | 7 | FR-0053 |
| M15 Approval Inbox | 1 | FR-0049 |
| M14 SOP Performance | 1 | KPI |
| M13 RMA Quality | 4 | FR-0048 |
| A10 SOP Feedback | 3 | FR-0051 |
| A12 AI Governance | 3 | FR-0050 |
| Reports | 2 | customer-satisfaction + operational-kpi |
| Admin Deprecation Metrics | 2 | P4 工具 |
| Admin V1 Inventory | 2 | P4 工具 |
| Admin Lifespan Health | 1 | 8-monitor health |

總計 **70+ 個新 endpoints**。

## §6 Rollback

若部署後發現重大問題：

```bash
# 1. Cloud Run revert 到上一個 revision
gcloud run services update-traffic api --to-revisions PREVIOUS_REV=100

# 2. DB migration 通常 forward-compatible（IF NOT EXISTS）
#    若需 rollback table 結構 — 對個別 migration 寫 reverse SQL
#    本 session 新表全是 ADD (CREATE TABLE / ADD COLUMN)，不影響 v1 caller
#    最差情況：保留 schema 改 deploy version 即可

# 3. 若 monitors crashed 卡死 — 改 env 暫停（見 background-monitors-runbook §5）
```

## §7 Post-deployment 驗證

1. `curl /api/v1/admin/lifespan-monitors/health` → `all_running=true`
2. `curl /api/v1/admin/v1-inventory` → 顯示所有 v1 endpoint
3. 跑 `python scripts/ops/check_monitors_health.py` exit 0
4. 在 GH Actions repo settings 加 secrets:
   - `STAGING_API_HOST`, `STAGING_ADMIN_JWT`
   - `PROD_API_HOST`, `PROD_ADMIN_JWT`
5. workflow_dispatch trigger `monitors-health.yml` 確認跑通
6. 24 hr 後查 `GET /api/v1/admin/deprecation/v1-metrics` 看 v1 流量 baseline

## §8 接下來工作

- WBS §8 P4 Cutover Stage 1-6 web caller 遷移 (3-5d，web e2e 需求)
- Reconciliation dual-sign UX rework (1-2d，前端產品工作)
- Phase 8 UAT 期程啟動
- Phase II 9 FR 完整版（從 MVP 補 §3 Phase II 啟動時需補項）

---

**本 release 完成後**：WBS 完成度 89% → ~98%；剩 ~2% 為 web-only UI / UAT 期程性工作。
