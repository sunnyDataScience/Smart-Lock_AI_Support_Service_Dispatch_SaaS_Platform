# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-Q2 Tactical Refactor

### Decisions

- **CR-0007 + ADR-0105** ⭐ — Door-check + Reschedule v2 contract 設計（2026-06-04 業主裁 §8 5 HD 全完）：HD-01=(a) 強制 arrival 前置；HD-02=(a) slots 1-3；HD-03=(a) SLA 24h；HD-04=(a) 獨立表；HD-05=(a) freeform jsonb。Migration 014 落地（saas.reschedule_proposal + CHECK + 3 indexes + updated_at trigger）。Service / Endpoints / Web caller 留下一 commit。詳見 [`docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md`](docs/architecture/adr/ADR-0105-reschedule-doorcheck-v2-design.md)。
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
