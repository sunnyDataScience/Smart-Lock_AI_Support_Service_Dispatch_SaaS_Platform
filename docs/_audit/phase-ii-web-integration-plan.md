---
id: PHASE-II-WEB-INTEGRATION-PLAN
title: Phase II 9 FR MVP — Web Integration Plan
status: open
created_at: 2026-06-05
related:
  - session-summary-2026-06-05.md
  - 9 FR MVP commits
purpose: 給未來 BUILD web 端對接 Phase II 9 FR MVP backend endpoints 的完整 plan。
---

# Phase II 9 FR MVP — Web Integration Plan

> Backend MVP 已全落地（49/44/53/50/51/48/45/46/47）；本 doc 規劃 web 端對接 step-by-step。

## §1 Integration Priority Matrix

按業務優先 + UI 複雜度排序：

| FR | Web Page Need | Complexity | Priority |
|:---|:---|:---:|:---:|
| FR-0049 Approval Inbox | admin dashboard widget | low | 🔥 高 |
| FR-0044 Tech Lifecycle | admin/technicians 加 6 actions | medium | 🔥 高 |
| FR-0045 Tech AP Statement | 技師 self-service + admin review | high | 🔥 高 |
| FR-0046 Dispatcher Commission | dispatcher self-service + admin | high | 中 |
| FR-0047 Brand B2B Settlement | brand portal (Phase III) + admin | very high | 中 |
| FR-0053 GDPR Forget | customer LIFF + admin queue | medium | 低 (合規) |
| FR-0048 RMA Quality | admin quality dashboard | medium | 中 |
| FR-0050 AI Governance | admin/observability dashboard | high | 低 (DPO) |
| FR-0051 SOP Feedback | KB owner page | medium | 中 |

## §2 Sprint Planning（建議 5 sprint）

### Sprint 1: Approval Inbox + Tech Lifecycle Actions (1 week)
- **頁面**: `admin/approval-inbox/page.tsx` (NEW)
  - 接 `GET /tenants/{tid}/approval-inbox` 列 5 type
  - filter: type / severity / days_overdue 
  - 顯示 envelope: type, summary, severity, days_overdue
  - click → 跳對應 page (scope_change → wo detail, refund → admin/refunds, etc.)
- **頁面**: `admin/technicians/page.tsx` (擴)
  - 加 6 action buttons (approve / reject / suspend / reactivate / terminate / view-events)
  - 接 `POST /tenants/{tid}/technicians/{id}:onboard-approve` etc.
  - lifecycle events tab 接 `GET .../lifecycle-events`
- **e2e**: `admin/approval-inbox.spec.ts` (smoke + filter)
- **e2e**: `admin/technicians-lifecycle.spec.ts` (狀態機驗)

### Sprint 2: Tech Statement self-service + admin (1 week)
- **頁面**: `account/statements/page.tsx` (NEW，技師端)
  - 接 `GET .../tech-statements?technician_id=me`
  - 列 monthly statements + dispute window 倒數
  - dispute 按鈕 + dispute_reason form
- **頁面**: `admin/accounting/tech-statements/page.tsx` (NEW)
  - admin 視角列全 statement
  - review / approve / reject / mark-paid 4 actions
- **e2e**: `account/statements.spec.ts` (self-service)
- **e2e**: `admin/accounting-tech-statements.spec.ts`

### Sprint 3: GDPR + AI Governance + SOP Feedback (1 week)
- **頁面**: `track/forget-request/page.tsx` (NEW，consumer LIFF)
  - 接 `POST /consumer/.../forget-requests`
  - 顯示 request status
- **頁面**: `admin/gdpr/forget-queue/page.tsx` (NEW)
  - 列 pending request + cooldown 倒數
  - legal-hold / soft-delete / hard-delete 3 actions
- **頁面**: `admin/observability/ai-governance/page.tsx` (NEW)
  - 接 `GET .../ai-governance/traces` + summary
  - 圖表: decision_type / guardrail_action / agent_version 分布
- **頁面**: `admin/knowledge-base/sop-feedback/page.tsx` (NEW)
  - 接 `GET .../sop-feedback?sop_id={id}/summary`
  - 顯示 sentiment_score / top low-rating / 5 source 分布

### Sprint 4: RMA Quality + Dispatcher Commission (1 week)
- **頁面**: `admin/quality/rma-findings/page.tsx` (NEW)
  - 接 4 endpoints (list / brand-summary / tech-summary / log)
  - 上傳 finding form
- **頁面**: `admin/accounting/dispatcher-commissions/page.tsx` (NEW)
  - 鏡像 Sprint 2 tech statement page
- **頁面**: `account/commission-statements/page.tsx` (NEW，dispatcher self)

### Sprint 5: Brand B2B Settlement + 整合 polish (1 week)
- **頁面**: `admin/accounting/brand-b2b/page.tsx` (NEW)
  - 接 AR/AP/NET 三 direction filter
  - net_payable_to dual-state UI
- **頁面**: Brand partner portal (Phase III scope，本 sprint skip)
- **polish**: 各 page TypeScript type 對齊 backend response

## §3 共用 API Client 增補

### 3.1 `web/src/lib/api-types.ts` 加入

從 `api/models/generated/` 或 backend openapi 同步生成：
- ApprovalInboxItem
- TechnicianLifecycleEvent
- TechStatement / DispatcherCommissionStatement / BrandB2bStatement
- ForgetRequest
- AiDecisionTrace
- SopFeedback
- RmaQualityFinding

### 3.2 `web/src/lib/api.ts` 加新 path helper（如需）

無需 — 全用 tenantPath() 即可。

## §4 共用 Component 增補

- `<ApprovalInboxItem>` — envelope 顯示卡片
- `<StatementStateBadge>` — 狀態徽章（6 狀態色票）
- `<DisputeWindowCountdown>` — 倒數計時器
- `<MonitorHealthLight>` — 紅綠燈（接 lifespan-monitors/health）

## §5 共用 i18n key

新 i18n key prefix:
- `admin.approvalInbox.*`
- `admin.technicianLifecycle.*`
- `account.statements.*`
- `admin.gdpr.*`
- `admin.aiGovernance.*`
- `admin.sopFeedback.*`
- `admin.rmaQuality.*`
- `admin.brandB2b.*`

繁中 + 英文兩語系。

## §6 e2e Test Coverage 目標

- Sprint 1-5 各 sprint：對應 page 至少 1 spec
- Coverage 目標：每 page 80% UI flow

## §7 工時估

| Sprint | 工時 |
|:---:|:---:|
| 1 | 5d (2 pages) |
| 2 | 5d (2 pages) |
| 3 | 5d (4 pages) |
| 4 | 5d (3 pages) |
| 5 | 3-5d (1 page + polish) |
| **Total** | **23-25 day** (~5 weeks 1 dev) |

可 2 dev 並行 → ~2.5 weeks。

## §8 Backend 已 ready (本 session 落)

所有 Phase II FR backend endpoint 已 100% mounted；
從 `GET /api/v1/admin/v1-inventory` 或 OpenAPI 取完整列表（11 new tags / 70+ endpoints）。

## §9 啟動條件

- [ ] Sprint planning approved by PM
- [ ] UI/UX wireframe approved (per FR)
- [ ] 11 SQL migrations 已套用 staging
- [ ] backend endpoint health check 通過

---

**啟動建議**：Sprint 1 (Approval Inbox + Tech Lifecycle) 為 highest business value 起點。
