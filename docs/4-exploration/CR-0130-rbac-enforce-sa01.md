# CR-0130: RBAC 轉 enforce——死角色收斂＋金流/派工/設定守衛落地（WBS 1.1.1 / SA-01）

- **日期**: 2026-07-09
- **狀態**: done（R1＋R2 全數完成 2026-07-09）
- **觸發面向**: 授權矩陣（security contract）、API 守衛、Domain model（角色目錄）
- **上游正典**: 13_Security §3.1/§3.2、ADR-005（deny-by-default）；前置 1.1.2（CR-0127）

## §1 對帳基線（runtime 反射，2026-07-09）

- 全 app 469 條路由：role_required 157／platform_admin 33／keeper·sod 守衛若干／
  require_tenant-only 239／公開（auth/consumer token/webhook/internal）其餘。
- **守衛含死角色端點 126 個**（FULL_ACCESS_ROLES 繼承 118＋硬編碼 8 處）→ 收斂後 **0**。
- **弱守衛寫入端點 117 個**（扣合法公開 92）→ 本輪收 49 → **殘餘 43**（R2 表）。

## §8 Human Decisions（業主 2026-07-09）

| # | 決策 | 裁決 |
|---|---|---|
| D1 | legacy 處置（13_Security §3.1 `[待確認]`）| ✅ **全面移除**：FULL_ACCESS_ROLES／8 處 router 硬編碼／RBAC_ADMIN_ROLES／ROLE_HIERARCHY 死角色與 legacy 值移除；矩陣刪 6 行 legacy（accounting/supervisor/auditor/family_reviewer/distributor/brand_oem）——矩陣＝7 角色正典＋line_user 通道行；殘存死角色 token 立即失效 |
| D2 | 弱守衛寫入收斂範圍 | ✅ **金流/派工/設定先＋技師動作白名單化**；其餘 43 個記 R2 對帳表下輪灰度 |

## §2 本輪落地（R1）

1. **死角色全面移除**（D1）：`deps.FULL_ACCESS_ROLES=("admin",)`（五個角色組常數連動收斂）；
   catalog/dispatch/invoices/quote/work_orders 系列 8 處硬編碼清理；`RBAC_ADMIN_ROLES={"admin"}`；
   `ROLE_HIERARCHY` 7 值；`_MATRIX`/`_ROLE_META` 刪 legacy 6 行；partner_scope bypass／
   quote gate override／main.py `_ADMIN_ROLES` 同步。
2. **守衛補齊 49 端點**（D2）：
   - 金流：inventory_v2 ×5→OPS；pricing calculate ×2→BACKOFFICE（技師零定價權 ADR-027）；
     warranty_claims→admin/cs/reviewer（矩陣 warranty.write）；refunds:agent-initiate→REVIEW
   - 派工：work_orders v1×12＋v2×9＋ops_v2×3——技師動作（accept/complete/簽名/到場/門況/
     延誤/用料/現場修正/改期）→ 新常數 `TECH_ACTION_ROLES`（BACKOFFICE＋technician）；
     小編動作（confirm/escalate/客戶改期代操作）→ BACKOFFICE；問題卡全寫入 ×10（含 convert 開單）→ BACKOFFICE
   - 設定：config_m18 slo-check→admin；scheduled_reports ×2→OPS；gdpr cancel→admin
3. 查證後**不動**：admin_schedule（`_admin_only` 既有守衛）、vouchers void（keeper 守衛）、
   media ×2（技師完工照上傳——require_tenant 維持，記 R2 評估）、
   escalate level 語彙 `tenant_admin`（升級對象標籤非登入角色，R2 更名）。

## §9 驗收

- 新 sweep 測試（test_cr_0130）：technician/vendor token 寫金流/派工/設定 8 樣本全 403；
  死角色 token 不再放行；技師動作端點不被誤鎖；7 角色正典一致性斷言。
- component **884 passed**（隔離 scratch @5448；rbac_dynamic/rbac_v2 legacy 斷言改寫正典）、
  unit 331、四站 tsc 0、types --check 冪等。

## R2 完成（2026-07-09 同日續輪）

37/43 端點收斂：kb（cases→BACKOFFICE、manuals/documents/export→OPS、search→BACKOFFICE）、
sop（起草→BACKOFFICE、review/adopt/dual/family/刪草稿→REVIEW、**技師回饋→TECH_ACTION**）、
conversations（代開/接管訊息/交接→BACKOFFICE）、sentiment ack→BACKOFFICE、
media ×2→TECH_ACTION（技師完工照）、resolution/resolve-suggest→BACKOFFICE、
family_reviews→REVIEW、rma/ai-governance→OPS、notifications push→OPS。

**定案保留 require_tenant（6＋1）**：自身通知操作 ×6（PATCH/bulk/mark-all-read v1+v2——
使用者操作自己的通知，技師亦需）；`consumer/bindings:generate-token`（**客戶**登入 web/track
的綁定流程，掛後台角色會鎖死客戶——與 vendor/客戶身分定位 `[待確認]` CR 同綁再議）。

驗收：R2 sweep 測試（technician/vendor 寫 10 樣本 403；技師 media/sop-feedback 白名單不誤鎖；
自身通知不被擋）；component 888 passed 零波及、unit 331、四站 tsc 0。

## R2 對帳表（原殘餘 43 個 require_tenant 寫入端點——上表為收斂結果）

kb（cases/manuals/documents/export）、sop（drafts/review/adopt/feedback）、conversations
（create/messages/resolve-handover）、notifications（self-scoped，多數屬使用者自身操作可留）、
sentiment alerts ack、media ×2（技師上傳需保留——建議 TECH_ACTION_ROLES）、resolution、
family_reviews、rma_quality、ai_governance traces、staff_applications submit（公開申請，by design）、
platform brand-applications submit（公開申請，by design）：

| module | method | path |
|---|---|---|
| notifications | PATCH | `/api/v1/notifications/{id}` |
| notifications | POST | `/api/v1/notifications/bulk` |
| notifications | POST | `/api/v1/notifications/mark-all-read` |
| notifications | POST | `/api/v1/notifications/push` |
| kb_cases | POST | `/api/v1/knowledge-base/cases` |
| kb_cases | PUT | `/api/v1/knowledge-base/cases/{id}` |
| kb_cases | DELETE | `/api/v1/knowledge-base/cases/{id}` |
| kb_cases | POST | `/api/v1/knowledge-base/cases/search` |
| kb_manuals | POST | `/api/v1/knowledge-base/manuals/upload` |
| kb_manuals | DELETE | `/api/v1/knowledge-base/manuals/{id}` |
| sop_drafts | POST | `/api/v1/sop-drafts` |
| sop_drafts | PATCH | `/api/v1/sop-drafts/{id}/review` |
| sop_drafts | POST | `/api/v1/sop-drafts/{id}/adopt` |
| family_reviews | POST | `/api/v1/family-reviews` |
| conversations | POST | `/api/v1/conversations` |
| conversations | POST | `/api/v1/conversations/{id}/messages` |
| sentiment_alerts | PATCH | `/api/v1/sentiment/alerts/{alert_id}` |
| media | POST | `/api/v1/media` |
| resolution | POST | `/api/v1/resolve` |
| kb_export | POST | `/api/v1/knowledge-base/export` |
| consumer_v2 | POST | `/consumer/bindings:generate-token` |
| sentiment_alerts_v2 | PATCH | `/tenants/{tenantId}/sentiment/alerts/{id}` |
| notifications_v2 | PATCH | `/tenants/{tenantId}/notifications/{notificationId}` |
| notifications_v2 | POST | `/tenants/{tenantId}/notifications:bulk` |
| notifications_v2 | POST | `/tenants/{tenantId}/notifications:mark-all-read` |
| conversations_v2 | POST | `/tenants/{tenantId}/conversations` |
| conversations_v2 | POST | `/tenants/{tenantId}/conversations/{id}/messages` |
| conversations_v2 | POST | `/tenants/{tenantId}/conversations/{id}/resolve-handover` |
| sops_v2 | POST | `/sops/{id}/review/dual` |
| sops_v2 | POST | `/sops/{id}/review/family` |
| sops_v2 | POST | `/tenants/{tenantId}/sops/drafts` |
| sops_v2 | DELETE | `/tenants/{tenantId}/sops/drafts/{draftId}` |
| sops_v2 | POST | `/tenants/{tenantId}/sops/drafts/{draftId}/adopt` |
| kb_v2 | POST | `/kb/documents` |
| kb_v2 | PUT | `/kb/documents/{docId}` |
| kb_v2 | DELETE | `/kb/documents/{docId}` |
| kb_v2 | POST | `/kb/documents:search` |
| kb_v2 | POST | `/kb/documents:export` |
| media_v2 | POST | `/tenants/{tenantId}/media` |
| resolution_v2 | POST | `/tenants/{tenantId}/problem-cards/{problemCardId}:resolve-suggest` |
| ai_governance_trace_v2 | POST | `/tenants/{tenantId}/ai-governance/traces` |
| sop_feedback_v2 | POST | `/tenants/{tenantId}/sop-feedback` |
| rma_quality_v2 | POST | `/tenants/{tenantId}/rma-quality-findings` |
