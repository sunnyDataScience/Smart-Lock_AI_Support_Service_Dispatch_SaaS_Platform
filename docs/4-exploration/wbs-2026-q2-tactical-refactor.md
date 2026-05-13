# WBS — 2026 Q2 戰術級重構（修正版）

**版本：** 2.0（對應 ADR-0024 修正版）
**日期：** 2026-05-11
**對應 ADR：** [ADR-0024](../1-decisions/ADR-0024-tier1-refactor-revised.md)（supersedes [ADR-0023](../1-decisions/ADR-0023-tactical-refactor-2026-q2.md)）

> **版本說明**：v1.0 對應 ADR-0023 初版；ADR-0023 於 hands-on 驗證後 supersede 為 ADR-0024，本 WBS 同步覆寫為 v2.0。
> v1.0 內容請查 git history（`git log -- docs/4-exploration/wbs-2026-q2-tactical-refactor.md`）。

> **範圍**：本 WBS 描述 Tier 1 架構審查 hands-on 修正後的 **5 個戰術級改進**，獨立於主合約交付的 `wbs-2026-q1.md`。

---

## 進度儀表板

| Phase | 狀態 | 工作量（修正後）| 可平行 | 風險 |
|-------|------|--------|--------|------|
| **0'** ADR-0024 + WBS v2 + CHANGELOG | IN PROGRESS | 0.5 天 | — | 無 |
| **1'** Tier 5 修 bug + gitignore | PENDING | **30 分鐘** | 與 2'/3'/4' 平行 | 無 |
| **2'** 頂層雜訊歸位 | PENDING | **1-2 小時** | 與 1'/3'/4' 平行 | 低 |
| **3'** web hooks 提煉 | PENDING | **1-2 天** | 與 4' 平行 | 低 |
| **4'** harness PIPELINE 列表化 | PENDING | **2-3 天 + staging 1 週** | 與 3' 平行 | **中**（agent 行為變更）|
| **5'** Flow INDEX（兩階段） | BACKLOG | 待 ROI 重估 | — | — |

**修正後總工期**：1 週內（不含 5' + staging）；含 staging 1 週合 main = **2 週**。
（原 ADR-0023 估 2-3 週；修正後縮減 50%+）

---

## 1.0 Phase 0' — ADR-0024 supersede + WBS v2 + CHANGELOG（0.5 天）

### 1.1 ADR-0024（本決策）
- **檔案**：`docs/1-decisions/ADR-0024-tier1-refactor-revised.md`
- **內容**：supersede ADR-0023 + 5 訊號 hands-on 驗證結果 + 修正後處方
- **依賴**：無

### 1.2 ADR-0023 狀態更新
- **動作**：
  - frontmatter `status: accepted` → `status: superseded`
  - frontmatter `superseded_by: []` → `superseded_by: [ADR-0024]`
  - 加 `related: ADR-0024`
  - 內文補 §8 變更紀錄（為何被 supersede）

### 1.3 本 WBS v2（覆寫 v1）
- **檔案**：`docs/4-exploration/wbs-2026-q2-tactical-refactor.md`
- **依賴**：ADR-0024

### 1.4 CHANGELOG.md 更新
- **檔案**：`CHANGELOG.md`
- **動作**：在 `[Unreleased] - 2026-Q2 Tactical Refactor` 章節補：
  - Decisions：ADR-0024 supersede ADR-0023 紀錄
  - Changed：WBS-Q2 v1 → v2
  - Notes：hands-on 修正歷程摘要

**PR**: `docs(adr): ADR-0024 supersede ADR-0023 — hands-on 修正版`

---

## 2.0 Phase 1' — Tier 5 修 bug + gitignore（30 分鐘）

> ADR-0024 §3 S4 — 從整套 generator 縮減為 3 行修正

### 2.1 修 `project-structure.md`
- **檔案**：`docs/5-views/project-structure.md`
- **動作**：
  - 第 30 行重複 `docs/` bug → 修正（其中一條應指 legacy 或刪除）
  - frontmatter `generator: manual (sunnydata-auto-regen TBD)` → `generator: manual`
  - frontmatter `last_updated: 2026-05-11`
  - 補一行附註：`web_design_spec_prompt_pipeline/` 標 legacy（待 Phase 2' 搬移）

### 2.2 `.gitignore` 補漏
- **檔案**：`.gitignore`
- **動作**：補 `.hypothesis/`、`.pytest_cache/`（Explore agent S3 發現）

### 2.3 驗收
- `git status --short` 確認 `.hypothesis/`、`.pytest_cache/` 不在 untracked
- markdown preview 看 project-structure.md 渲染正常

**PR**: `chore(docs): fix project-structure.md duplicate docs/ bug + gitignore .hypothesis .pytest_cache`

---

## 3.0 Phase 2' — 頂層雜訊歸位（1-2 小時）

> ADR-0024 §3 S3 — 從 4 動作縮減為 2 動作（保留 CLAUDE_TEMPLATE.md、不改名 api/data）

### 3.1 `report/` → `docs/releases/`
- **動作**：
  - `git mv report docs/releases`
  - 更新所有引用：grep `report/` 確認無 deploy script / hook 引用
  - 補 `docs/releases/README.md` 說明 v1.x.x 版本歷史

### 3.2 `web_design_spec_prompt_pipeline/` → `docs/legacy/`
- **動作**：
  - `git mv web_design_spec_prompt_pipeline docs/legacy/web_design_spec_prompt_pipeline`
  - 補 `docs/legacy/web_design_spec_prompt_pipeline/README.md`：標明「已遷出，僅保留歷史，不再維護」
  - 更新 `docs/5-views/project-structure.md` 移除頂層 `web_design_spec_prompt_pipeline/` 引用

### 3.3 處理 `api/agent/integrations/` 空目錄（ADR-0024 E3）
- **動作**：
  - `ls api/agent/integrations/` 確認真為空
  - 若為空且 grep 無引用 → `rmdir`
  - 若有 .gitkeep 但無 code → 補 README 說明保留原因，或刪除

### 3.4 驗收
- `grep -rn "report/\|web_design_spec_prompt_pipeline" --include="*.sh" --include="*.yml" --include="*.toml"` 無殘留
- repo root `ls` 後檢視：4 大模組 + 標準工具目錄 + docs + .claude，無 legacy 殘留

**PR**: `refactor(repo): relocate report/ → docs/releases/, legacy pipeline → docs/legacy/`

---

## 4.0 Phase 3' — web hooks 提煉（1-2 天）

> ADR-0024 §3 S1 — 從新增 api/ + hooks/ 雙層縮減為單一 hooks/ 層

### 4.1 設計原則
- **不動** `web/src/lib/api.ts`（raw HTTP client，已成熟）
- **不動** `web/src/lib/cache.ts`（30s staleTime + promise dedup，已整合）
- **不引入** SWR（lib/cache.ts 已具備所需功能）
- **不新增** `web/src/api/` 層（cache layer 已存在）
- **新增** `web/src/hooks/` 統一位置 + 提煉 `usePaginatedFetch`

### 4.2 Phase 3.1 — 遷移既有 lib/use*.ts（1 PR）
- **動作**：
  - `git mv web/src/lib/useSSEChannel.ts web/src/hooks/useSSEChannel.ts`
  - `git mv web/src/lib/useBroadcast.ts web/src/hooks/useBroadcast.ts`
  - `git mv web/src/lib/useRealtimeChannel.ts web/src/hooks/useRealtimeChannel.ts`
  - grep + 修所有 import path

**PR**: `refactor(web): consolidate hooks under src/hooks/ (move from src/lib/)`

### 4.3 Phase 3.2 — 新增 usePaginatedFetch（1 PR）
- **檔案**：`web/src/hooks/usePaginatedFetch.ts`（新增）
- **動作**：提煉 setLoading/setError + error envelope 處理 + 整合 `lib/cache.ts`
- **驗收**：unit test 通過；至少 2 個 pilot page 改用後仍正常

**PR**: `feat(web): add usePaginatedFetch hook for loading/error/cache abstraction`

### 4.4 Phase 3.3 — 改寫 13 個直接 import api 的 page.tsx（1-2 PR）
- **目標**：grep `import.*from.*@/lib/api` 找出的 13 個 page，改用 `usePaginatedFetch` 或既有 hook
- **PR 拆分策略**：按 domain 群組（如 5-7 個 PR per group）
- **驗收**：每 PR 對應頁面手動測試 + lint + build

**PR**: 多個 `refactor(web): migrate <domain> pages to usePaginatedFetch`

---

## 5.0 Phase 4' — harness PIPELINE 列表化（2-3 天 + staging 1 週）

> ADR-0024 §3 S2 — 從 declarative pipeline + dark launch + 3 phase 縮減為「PIPELINE 清單常數 + 迴圈」

### 5.1 設計
- **新增** `agent/harness/__init__.py`（如已存在則加入）：
  ```python
  from . import safety_gate, data_correction, quick_reply, intent_handler
  from . import skills_prefix, validator_pipeline, profile_updater
  from . import pc_creator, memory_manager, agent_audit

  PIPELINE = [
      safety_gate, data_correction, quick_reply, intent_handler,
      skills_prefix, validator_pipeline, profile_updater,
      pc_creator, memory_manager, agent_audit,
  ]
  ```
- 各 sibling module 補 `async def apply(ctx)` 介面
- `orchestrator.py` `agent_and_reply()` 改 `for layer in PIPELINE: await layer.apply(ctx)`

### 5.2 不做的事
- ❌ 不新增 `pipeline.py` 與 `context.py`
- ❌ 不新增 `[harness.pipeline]` config 區塊
- ❌ 不做 feature flag / dark launch
- ❌ 不分 3 phase migration（直接全切，但測試完整）

### 5.3 驗收
- **本地**：`uv run python -m quality.quality_check` + `evals.runner` diff=0
- **staging (dev branch)**：合到 dev 後跑 quality_check + evals **連續 7 天**
  - 自動化檢查：`scripts/ci/staging-watchdog.sh`（新增，每日 cron 跑 quality_check + 比對基準）
  - 若 7 天內任一指標退化 → 立即 revert
- **合 main**：staging 通過後才合

**PR（拆分）**：
1. `refactor(harness): add apply(ctx) interface to all sibling modules`
2. `refactor(harness): introduce PIPELINE list constant + orchestrator loop`

---

## 6.0 Phase 5' — Flow INDEX（BACKLOG，待 ROI 重估）

> ADR-0024 §3 S5 — 拆兩階段、工期 0.5 週 → 1-1.5 週；先進 backlog

### 6.1 拆分

| 子階段 | 動作 | 工期 |
|---|---|---|
| 5.1 | 補 25 BF/SF + 25 FR frontmatter `related_apis: []` 欄位 | 3-5 天（手工）|
| 5.2 | INDEX.md generator 自動聚合 frontmatter | 0.5 天 |

### 6.2 BACKLOG 條件
- Phase 1'-4' 完成後重估 ROI
- 若 V3 多通道擴展時程明確 → 啟動
- 若 V3 延後超過 3 個月 → 從 backlog 移除（避免 over-optimization）

---

## 7.0 風險登錄（修正後）

| 風險 | 機率 | 影響 | 緩解 |
|---|---|---|---|
| Phase 1' 修 bug 後 generator 認知混亂 | 低 | 低 | frontmatter 明確標 `generator: manual` |
| Phase 2' `report/` 搬移漏改引用 | 低 | 低 | git mv 保留歷史；grep 完整掃描 |
| Phase 3' `usePaginatedFetch` 抽象漏 case | 中 | 中 | 先做 2 page pilot 驗證；其餘漸進遷移 |
| Phase 4' PIPELINE 切換行為偏差 | 中 | **高**（agent 行為變更）| staging 7 天 + watchdog 自動比對 baseline |
| Phase 4' staging watchdog 漏網 | 中 | **高** | watchdog 補多指標：LLM cost、response time、錯誤率、quality_check 分數 |
| 既有 sync hook 持續干擾 working tree | 高 | 低 | 每次 commit 精準 stage，不用 `git add .` |

---

## 8.0 驗收條件（Phase 1'-4' 完成）

- [ ] ADR-0024 merge；ADR-0023 標 superseded
- [ ] `docs/5-views/project-structure.md` bug 已修；frontmatter generator 為 manual
- [ ] `.gitignore` 涵蓋 `.hypothesis/`、`.pytest_cache/`
- [ ] `docs/releases/` 與 `docs/legacy/web_design_spec_prompt_pipeline/` 已建立
- [ ] `web/src/hooks/` 已建立並涵蓋既有 3 個 use*.ts + 新增 usePaginatedFetch
- [ ] 13 個直接 import api 的 page 已遷移
- [ ] `agent/harness/__init__.py` PIPELINE 列表；orchestrator 改用迴圈
- [ ] staging 7 天 quality_check + evals 零退化
- [ ] CHANGELOG.md 完整記錄

---

## 9.0 變更紀錄

| 日期 | 版本 | 內容 |
| :--- | :--- | :--- |
| 2026-05-11 | v1.0 | 初版 — 對應 ADR-0023 |
| 2026-05-11 | v2.0 | 對應 ADR-0024 supersede ADR-0023；5 Phase 範圍縮減 50%+；S5 改為 BACKLOG |
