# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-Q2 Tactical Refactor

### Decisions

- **CR-0012 opened — FR-0012 技師月結撥款 CIA**（branch `docs/cr-0012-fr-0012-monthly-settlement-cia`，2026-06-04）：CR-0010 HD-03=a batch 第 2 件。FR-0012 為 V1.0 金流閉環另一半（CR-0011 客戶付平台 + CR-0012 平台付技師）。取證確認：`settlements_v2.trigger_monthly_settlement` 為 **501 stub**（Phase II 標記）、`settlement_service` 無 monthly trigger / compute_payouts / payout_via_bank、BR-M12-NN 5 條未編號、ADR-0041 (travel fee 80/20) accepted 但 split 邏輯未進計算公式。CIA 列 **6 HD** 待業主裁決：(1) Bank payout provider（台銀 / 第三方 AP / manual CSV / 階段化）、(2) Cron 排程實作（APScheduler / Cloud Scheduler / pg_cron / GitHub Actions）、(3) Bank 3-retry 策略、(4) manual_payout 完結機制、(5) Dispute 排除實作（即時查 / flag-driven / 雙保險）、(6) Escrow 模型（**鏡像 CR-0011 HD-08，須同步裁決避免金流方向矛盾**）。建議 HD-01=(c) manual CSV 階段化 → 解 vendor 契約 review 拖延風險。status: `open-awaiting-decisions`。詳見 [`docs/_audit/CR-0012-fr-0012-monthly-settlement-cia.md`](docs/_audit/CR-0012-fr-0012-monthly-settlement-cia.md)。

- **CR-0009 + ADR-0106** ⭐⭐ — Agent caller migration P4-T1 **全鏈路完工**（2026-06-04 一日內）：4 個 agent v1 caller（app.py 2 + admin_api.py 2）全部遷 v2；新增 2 個 admin reschedule v2 endpoints + 1 個 refunds:agent-initiate single-actor endpoint；ADR-0106 記錄 LangGraph 特例不違背全面 SoD 原則。**agent v1 caller = 0**（解開 P4 cutover 唯一硬 gate per CR-0003 §3）。
- **CR-0005 / 0006 / 0009 §8 全裁完** ⭐⭐⭐（2026-06-04 業主三輪 AskUserQuestion 拍完 9 個剩餘 HD）：
  * CR-0005 HD-06 = (a) CSV 為主，JSON 可選（query format 切換）→ 6/6 HD 全裁
  * CR-0006 HD-02=a 軟刪 / HD-03=a 共用 kb_audit_log（doc_type='sop'）/ HD-04=a 廢棄舊 /sops/family-reviews / HD-05=a 即時查 SLA → 5/5 HD 全裁
  * CR-0009 HD-01=a `/consumer/work-orders/{token}/reschedule:{action}` / HD-03=a CR-0006 先拍板再做 / HD-04=a 無 canary / HD-05=a 任何 v1 404 即 PagerDuty → 5/5 HD 全裁
  * 累計 6 CR §8 = 26/26 HD 全裁完，CIA gate 全清；後續純實作 work
- **CR-0005 + ADR-0103** ⭐ — KB v2 expand 設計（2026-06-04 業主裁 §8 6/6 HD 全完）。Migration 015 落地（case_entries.deleted_at + manuals.deleted_at + saas.kb_audit_log + 4 indexes 含 90d hot partial）。Step 2/3：PUT + DELETE + :search endpoints 落地。Step 3/3：2 個 DELETE web caller 遷完；剩 GET/PUT/POST/search UI shape 改造 + :upload (ClamAV) + :export 待後續 commit。詳見 [`docs/architecture/adr/ADR-0103-kb-v2-expand-design.md`](docs/architecture/adr/ADR-0103-kb-v2-expand-design.md)。
- **CR-0007 + ADR-0105** ⭐⭐ — Door-check + Reschedule v2 contract **全鏈路落地**（schema + service + endpoints + web caller，2026-06-04 一日完工）。業主裁 §8 5 HD 全完，三 step：
  * step 1/3 schema：migration 014 `saas.reschedule_proposal` + ADR-0105
  * step 2/3 backend：`work_order_service.submit_door_check_v2`（arrival 前置 409 guard）+ `propose_reschedule_v2`（INSERT 獨立表）；`work_orders_v2:POST .../door-check` + `work_orders_ops_v2:POST .../reschedule:propose`
  * step 3/3 frontend：`my-orders/[id]/door-check/page.tsx` + `work-orders/[id]/page.tsx` 改 v2 tenantPath
  本 branch 真實 v1 caller 43 → 40（door-check + reschedule + settlements 三筆 -3）。詳見 [`docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md`](docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md)。
- **CR-0008** ⭐ — Settlements GET list v2 落地（2026-06-04 業主裁 HD-01=last_3_months / HD-02=period_end_desc）。`settlement_service.list_settlements` 擴 `period_filter` + `sort_by` 參數，v1 預設不變；`settlements_v2.py` 補 `GET /tenants/{tid}/settlements`；`web/accounting/page.tsx` settlement 列表遷 v2。CR-0008 §8 全裁，status: decided-and-implemented。
- **CR-0010** ⭐ — FR-0019 動態 RBAC 角色管理 `status: draft → active`（2026-06-04 業主裁 HD-01=a）。取證 content-complete + ADR-0042 accepted + code 全部實作（role_service publish + rbac_v2 endpoint + RbacChangedBanner mount）。Draft FR 5 → 4，北極星 (1) 真實推進。詳見 [`docs/_audit/CR-0010-fr-0019-promote-to-active.md`](docs/_audit/CR-0010-fr-0019-promote-to-active.md)。
- **跨 CR 部分裁決**（2026-06-04 同 session）：
  * CR-0005 HD-01 = (a) 保留 meta-wrapping（KB v2 響應 shape，連動 CR-0006 HD-01 = a）
  * CR-0007 HD-01 = (a) door-check 強制 arrival 前置（無 arrived_at → 409）
  * CR-0009 HD-02 = (a) 新增 v2 single-actor `refunds:agent-initiate`（保留 agent 自動退款；待 ADR-0106 記 LangGraph 特例）
  * CR-0010 HD-03 = (a) 同步開 CR-0011~0014 審查其他 4 draft FR
  CR-0005/0006/0007/0009 仍有其他 HD 未裁，實作仍卡。
- **ADR-0025** ⭐ — Harness 採 branching pipeline，PIPELINE list 為 introspection-only。Phase 4' hands-on 後從「linear PIPELINE + apply(ctx)」縮減為「結構化 PIPELINE 常數 + 各 layer module PHASE 常數」，零 runtime 變更不需 staging。詳見 [`docs/1-decisions/ADR-0025-harness-branching-pipeline.md`](docs/1-decisions/ADR-0025-harness-branching-pipeline.md)。
- **ADR-0024** — Tier 1 戰術級重構（2026 Q2）**hands-on 修正版**，supersedes ADR-0023。5 訊號處方修正、3 處事實錯誤修正、工期 2-3 週 → 1 週內。詳見 [`docs/1-decisions/ADR-0024-tier1-refactor-revised.md`](docs/1-decisions/ADR-0024-tier1-refactor-revised.md)。Phase 4' 實作見 §9 修正紀錄。
- **ADR-0023** — 已 **superseded by ADR-0024**。原文保留作為決策足跡；merge 後 30 分鐘 hands-on 階段發現 4/5 訊號處方不合理 + 3 處事實錯誤（ADR-0010 懸空、UF 系統未實作、`api/agent/integrations/` 空目錄）。

### Added

- `MISSION.md`（root）— Claude Code 持續迭代任務書（北極星 6 條完工條件 + 階段優先 + per-stage 驗收 + 紅線清單；含 Reality Check 與 session 進度日誌），供 `/goal @MISSION.md` 鎖 session 用
- `docs/architecture/adr/ADR-0106-agent-single-actor-refund-langgraph-exception.md` — agent 自動退款單簽特例正典（CR-0009 HD-02=a）
- `api/routers/work_orders_ops_v2.py` 新增 2 endpoints：customer-confirm + customer-reject（CR-0009 admin path；agent JWT 呼叫）
- `api/routers/refunds_v2.py:130+` 新增 POST `:agent-initiate`（HD-02 single-actor，role enforce agent|system）
- `agent/app.py:387` + `:407` customer-confirm/reject 改 v2 tenant path
- `agent/integrations/admin_api.py:282` refunds 改 `:agent-initiate`
- `agent/integrations/admin_api.py:356` sop-drafts 改 v2 tenant-scoped path
- `SQL/migrations/016-sop-v2-list-expand.sql` — sop_drafts.deleted_at + kb_audit_log doc_type CHECK 擴 'sop'
- `docs/architecture/adr/ADR-0104-sop-v2-list-design.md` — CR-0006 §8 5 HD 決策 ADR
- `api/routers/sops_v2.py` 新增 6 endpoints：GET list / GET single / POST create / DELETE soft / GET family-reviews list / GET family-reviews:pending（CR-0006 step 2/3 落地）
- `api/services/sop_draft_service.py:soft_delete_draft` 新增（HD-02 軟刪）
- `api/services/sop_draft_service.py:list_drafts / get_draft` 加 `deleted_at IS NULL` 過濾
- `web/src/lib/kb-adapter.ts:kbDocumentToSopDraft` 新增（meta-wrap → flat SopDraft）
- `web/src/app/knowledge-base/sop-drafts/[id]/page.tsx` GET + refresh GET 改 v2 + adapter（2 caller 遷完）
- `api/routers/kb_v2.py:660+` POST /kb/documents:export（HD-06=a CSV-first，?format=json 切換；MVP case only；EXPORT_MAX=10000）
- `web/src/app/knowledge-base/cases/page.tsx:161` search caller 從 v1 改打 v2 :search + kbDocumentToCaseEntry adapter
- `web/src/lib/kb-adapter.ts` 新增 — `KBDocument` interface + `kbDocumentToCaseEntry` adapter（CR-0005 step 3/3 解 meta-wrap shape 與 UI flat shape 不一致）
- `web/src/app/knowledge-base/cases/[id]/page.tsx` GET → v2 + adapter
- `web/src/app/knowledge-base/cases/[id]/edit/page.tsx` GET + PUT → v2 + adapter
- `web/src/app/knowledge-base/cases/new/page.tsx` POST → v2 + doc.id 導頁
- `api/routers/kb_v2.py:360+` 新增 CR-0005 step 2/3：
  * `_write_kb_audit_log` helper（best-effort 寫 saas.kb_audit_log，失敗 log warn 不阻擋）
  * `PUT /kb/documents/{docId}`（doc_type 自動 fallback / case 完整支援 / manual 暫 501 待 update_manual impl）
  * `DELETE /kb/documents/{docId}`（軟刪 case_entries SET is_active=FALSE + deleted_at=NOW；manuals SET deleted_at=NOW；before-snapshot 寫 audit；204）
- `api/services/manual_service.py:list_manuals` 加 `deleted_at IS NULL` 過濾（CR-0005 HD-02 軟刪兼容）
- `api/routers/kb_v2.py:get manual` 加 `deleted_at IS NULL` 過濾
- `SQL/migrations/015-kb-v2-expand.sql` — CR-0005 step 1/3：case_entries.deleted_at + manuals.deleted_at + saas.kb_audit_log（pending psql apply）
- `docs/architecture/adr/ADR-0103-kb-v2-expand-design.md` — CR-0005 §8 4/6 HD 決策 ADR
- `api/services/work_order_service.py` 新增：
  * `submit_door_check_v2`（HD-01 強制 arrival 前置：查 work_order_events arrival → 409）
  * `propose_reschedule_v2`（INSERT saas.reschedule_proposal；HD-02 slots 1-3 驗證 + send_via line/sms/email）
- `api/routers/work_orders_v2.py:560+` 新增 `POST /tenants/{tid}/work-orders/{id}/door-check`（CR-0007 / `_DoorCheckSubmitRequest`）
- `api/routers/work_orders_ops_v2.py:330+` 新增 `POST /tenants/{tid}/work-orders/{id}/reschedule:propose`（CR-0007 / `_ProposeRescheduleV2Body` + `_ProposedSlot`）
- `web/src/app/my-orders/[id]/door-check/page.tsx:161` v1 → v2 `tenantPath(/work-orders/{id}/door-check)`
- `web/src/app/work-orders/[id]/page.tsx:1076` v1 → v2 `tenantPath(/work-orders/{id}/reschedule:propose)`；移除 setOrder（v2 propose 不變更 scheduled_at，待 RSVP 後 confirm）
- `SQL/migrations/014-reschedule-proposals.sql` — saas.reschedule_proposal 表（CR-0007 落地步驟 1/3；pending psql apply）
- `docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md` — CR-0007 §8 5 HD 決策正式落地 ADR
- `SQL/migrations/MIGRATION_REGISTRY.md`：014 row 加入（pending-apply 狀態標記）
- `api/routers/settlements_v2.py:75-130` 新增 `GET /tenants/{tid}/settlements` v2 endpoint（CR-0008 落地；預設 last_3_months + period_end desc）
- `api/services/settlement_service.py` `list_settlements` 擴 `period_filter` / `sort_by` 參數（v1 預設不變，向後相容）
- `docs/_audit/CR-0007-door-check-reschedule-contract.md` — door-check + reschedule contract 重設計 CIA（5 HD，HD-01 已裁）
- `docs/_audit/CR-0008-settlements-get-list-v2.md` — 最小 CIA（2 HD，本 session 全裁完並實作）
- `docs/_audit/CR-0009-agent-caller-migration-p4-t1.md` — agent caller P4-T1 CIA（5 HD，HD-02 已裁）
- `docs/_audit/CR-0010-fr-0019-promote-to-active.md` — FR-0019 promotion CIA（3 HD，HD-01/02/03 已裁並實作）
- `docs/_audit/CR-0005-kb-v2-expand-and-shape.md` — KB v2 expand CIA（PUT/DELETE/search/export/upload + 響應 shape 6 HD），解 9 個 v1 caller 遷移路徑
- `docs/_audit/CR-0006-sop-v2-list-expand.md` — SOP v2 list expand CIA（sop-drafts + family-reviews list/CRUD 5 HD），解 5 個 v1 caller
- `web/src/components/layout/AuthGuard.tsx`：mount RbacChangedBanner（之前定義未掛載），補齊 RBAC realtime 全鏈路
- `web/src/app/accounting/page.tsx:124` settlement list 從 `/api/v1/accounting/settlements?limit=50` 遷至 v2 `tenantPath("/settlements?limit=50")`（CR-0008 落地）
- `docs/4-exploration/WBS-0004-phase-5-flow-index-backlog-2026-q2.md` — Phase 5' Flow INDEX defer 紀錄 + T1-T4 啟動條件 / R1-R2 移除條件
- `docs/4-exploration/WBS-0003-phase-3.3-backlog-2026-q2.md` — Phase 3.3 backlog 推進紀錄（最終 16/18 page + hook 演化 5→8 features）
- `docs/1-decisions/ADR-0025-harness-branching-pipeline.md` — Phase 4' 修正版 ADR
- `docs/1-decisions/ADR-0024-tier1-refactor-revised.md` — 修正版 ADR（含 Phase 4' §9 修正紀錄）
- `docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md` — 初版 ADR（已 superseded）
- `docs/4-exploration/WBS-0002-2026-q2-tactical-refactor.md` — 對應 WBS v2.0（覆寫 v1.0）
- `CHANGELOG.md`（本檔）
- `agent/harness/__init__.py`：由空檔變為 PIPELINE 結構化常數 + PipelineEntry NamedTuple + module docstring（per ADR-0025）
- `agent/harness/{safety_gate,data_correction,quick_reply,intent_handler,pc_creator,profile_updater,validator_pipeline,memory_manager,agent_audit}.py`：各加 `PHASE: str` 模組層級常數（per ADR-0025）
- `web/src/hooks/`：新增目錄，含 5 個 hook（useRealtimeChannel, useSSEChannel, useBroadcast 自 lib/ 遷移；usePaginatedFetch 新增）+ README
- `docs/1-decisions/releases/`：83 個 v1.x.x.md release notes（自 root `report/` 遷移）
- `docs/_archive/legacy/web_design_spec_prompt_pipeline/`：legacy 設計系統 pipeline（自 root 遷移）

### Changed

- `web/src/app/admin/schedule-requests/page.tsx`：reject 從 `POST /api/v1/admin/schedule-requests/{id}/reject` 遷至 v2 `POST /tenants/{tid}/exceptions/{id}:approve`（body.decision="reject" 區分）；移除 P3-KEEP flat 註解（原註解「reject 無對應 v2 端點」與 exceptions_v2.py:33 不符，實為文件 stale）
- `web/src/components/admin/CustomerForm.tsx`、`web/src/app/admin/customers/[id]/edit/page.tsx`：docstring 同步至 v2 路徑（實際 caller 早已 v2，註解 stale）
- `web/docs/system-completion-status.md`：P3.5 Track-B caller 補遺改標 ✅ 100%（2026-06-04 取證收尾，原表述 stale）；總體 88% → 89%；架構遷移 85% → 88%；Caller 遷移 v1→v2 80% → 92%；§8 P0 移除已完成的 P3.5 條目、新增 P1「Reconciliation dual-sign UX rework」backlog
- `docs/_audit/CR-0003-full-cutover-wbs.md`：新增 §5 進度區（append-only），標記 P0/P1/P2/P3/P3.5 ✅、P4 ⏳
- `MISSION.md`：P3.5 驗收條件改標 ✅ 已收尾；迭代優先順序更新為「P4 Cutover 目前在這」+ 並行 backlog 區段
- `docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md`：frontmatter `status: superseded`、`superseded_by: [ADR-0024]`；補 §8 變更紀錄
- `docs/4-exploration/WBS-0002-2026-q2-tactical-refactor.md`：v1 → v2（5 Phase 範圍縮減 50%+；S5 改為 BACKLOG）
- `.gitignore`：新增 `api/data/`、`web/test-results/` 兩條（runtime 產物，含個資不入版控）
- `web/src/lib/api.ts`：檔頭註解路徑指向新位置 `web/types/api.generated.ts`（取代舊路徑 `docs/02-design/specs/generated/...`）

### Notes

本章節為 Q2 戰術級重構期間累積，待全部 Phase 1'-4' 完成後另開 release tag。

**Hands-on 修正歷程**：ADR-0023 於 2026-05-11 PR #62 merge 後 30 分鐘，進入 Phase 1.1 hands-on 階段。先發現 `report/` 是 95 個 v1.x.x release notes（非垃圾）、`api/data/` 命名類比錯誤，繼派 3 個 Explore agent 對全 5 訊號做深度驗證，揭露 4/5 處方不合理 + 3 處事實錯誤。Supersede 為 ADR-0024（hands-on 修正版），整體工期估計從 2-3 週縮減為 1 週內。決策軌跡保留作為「假設驅動 → hands-on 驗證」學習案例。

---

## [Historical] — Pre-2026-Q2

> 2026-Q2 之前的變更未維護於本檔。歷史紀錄請參考：
>
> - Git commit history（`git log --oneline`）
> - 各模組 module-boundary 文件（`docs/1-decisions/module-boundary/*.md`）
> - WBS Q1 進度（`docs/4-exploration/WBS-0001-2026-q1.md`）
