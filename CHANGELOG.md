# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-Q2 Tactical Refactor

### Decisions

- **ADR-0025** ⭐ — Harness 採 branching pipeline，PIPELINE list 為 introspection-only。Phase 4' hands-on 後從「linear PIPELINE + apply(ctx)」縮減為「結構化 PIPELINE 常數 + 各 layer module PHASE 常數」，零 runtime 變更不需 staging。詳見 [`docs/1-decisions/ADR-0025-harness-branching-pipeline.md`](docs/1-decisions/ADR-0025-harness-branching-pipeline.md)。
- **ADR-0024** — Tier 1 戰術級重構（2026 Q2）**hands-on 修正版**，supersedes ADR-0023。5 訊號處方修正、3 處事實錯誤修正、工期 2-3 週 → 1 週內。詳見 [`docs/1-decisions/ADR-0024-tier1-refactor-revised.md`](docs/1-decisions/ADR-0024-tier1-refactor-revised.md)。Phase 4' 實作見 §9 修正紀錄。
- **ADR-0023** — 已 **superseded by ADR-0024**。原文保留作為決策足跡；merge 後 30 分鐘 hands-on 階段發現 4/5 訊號處方不合理 + 3 處事實錯誤（ADR-0010 懸空、UF 系統未實作、`api/agent/integrations/` 空目錄）。

### Added

- `MISSION.md`（root）— Claude Code 持續迭代任務書（北極星 6 條完工條件 + 階段優先 + per-stage 驗收 + 紅線清單），供 `/goal @MISSION.md` 鎖 session 用
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
