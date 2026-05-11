# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-Q2 Tactical Refactor

### Decisions

- **ADR-0023** — Tier 1 戰術級資料夾與整合層重構（2026 Q2）。保留 6-tier docs 結構與 4 大 first-class 模組邊界，執行 5 個戰術級改進，分 5 Phase 漸進交付。詳見 [`docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md`](docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md) 與 WBS [`docs/4-exploration/wbs-2026-q2-tactical-refactor.md`](docs/4-exploration/wbs-2026-q2-tactical-refactor.md)。

### Added

- `docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md` — 戰術級重構 ADR
- `docs/4-exploration/wbs-2026-q2-tactical-refactor.md` — 對應 WBS
- `CHANGELOG.md`（本檔）

### Changed

- `.gitignore`：新增 `api/data/`、`web/test-results/` 兩條（runtime 產物，含個資不入版控）
- `web/src/lib/api.ts`：檔頭註解路徑指向新位置 `web/types/api.generated.ts`（取代舊路徑 `docs/02-design/specs/generated/...`）

### Notes

本章節為 Q2 戰術級重構期間累積，待全部 5 Phase 完成後另開 release tag。

---

## [Historical] — Pre-2026-Q2

> 2026-Q2 之前的變更未維護於本檔。歷史紀錄請參考：
>
> - Git commit history（`git log --oneline`）
> - 各模組 module-boundary 文件（`docs/1-decisions/module-boundary/*.md`）
> - WBS Q1 進度（`docs/4-exploration/wbs-2026-q1.md`）
