# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-Q2 Tactical Refactor

### Decisions

- **ADR-0024** ⭐ — Tier 1 戰術級重構（2026 Q2）**hands-on 修正版**，supersedes ADR-0023。5 訊號處方修正、3 處事實錯誤修正、工期 2-3 週 → 1 週內。詳見 [`docs/1-decisions/ADR-0024-tier1-refactor-revised.md`](docs/1-decisions/ADR-0024-tier1-refactor-revised.md)。
- **ADR-0023** — 已 **superseded by ADR-0024**。原文保留作為決策足跡；merge 後 30 分鐘 hands-on 階段發現 4/5 訊號處方不合理 + 3 處事實錯誤（ADR-0010 懸空、UF 系統未實作、`api/agent/integrations/` 空目錄）。
- **ADR-0025** — 預留給 Phase 4' harness PIPELINE 切換決策（原 ADR-0023 預留 0024，因 ADR-0024 占用，下移）。

### Added

- `docs/1-decisions/ADR-0024-tier1-refactor-revised.md` — 修正版 ADR
- `docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md` — 初版 ADR（已 superseded）
- `docs/4-exploration/wbs-2026-q2-tactical-refactor.md` — 對應 WBS v2.0（覆寫 v1.0）
- `CHANGELOG.md`（本檔）

### Changed

- `docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md`：frontmatter `status: superseded`、`superseded_by: [ADR-0024]`；補 §8 變更紀錄
- `docs/4-exploration/wbs-2026-q2-tactical-refactor.md`：v1 → v2（5 Phase 範圍縮減 50%+；S5 改為 BACKLOG）
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
> - WBS Q1 進度（`docs/4-exploration/wbs-2026-q1.md`）
