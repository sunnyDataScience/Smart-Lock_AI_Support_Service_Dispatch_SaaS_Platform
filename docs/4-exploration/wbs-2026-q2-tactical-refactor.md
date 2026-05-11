# WBS — 2026 Q2 戰術級重構

**版本：** 1.0
**日期：** 2026-05-11
**對應 ADR：** [ADR-0023](../1-decisions/ADR-0023-tactical-refactor-2026-q2.md)
**對應 plan：** `~/.claude/plans/home-sunny-python-workstation-github-sm-snuggly-cascade.md`

> **範圍說明**：本 WBS 描述 Tier 1 架構審查產出的 **5 個戰術級改進**，獨立於主合約交付的 `wbs-2026-q1.md`（Phase 0-9 甲方合約面）。本 WBS 是 **內部工程任務**，不影響 V1.0/V2.0 對外承諾。

---

## 進度儀表板

| Phase | 狀態 | 工作量 | 可平行 | 風險 |
|-------|------|--------|--------|------|
| **0** ADR + WBS + CHANGELOG | IN PROGRESS | 0.5 天 | — | 無 |
| **1.1** 頂層雜訊 + api/data → api/storage | PENDING | 1 天 | 與 1.2/2/3 平行 | 低 |
| **1.2** project-structure.md generator | PENDING | 1 天 | 與 1.1/2/3 平行 | 低 |
| **2** web/src/{api,hooks}/ + SWR | PENDING | 1 週 | 與 3 平行 | 中 |
| **3** harness declarative pipeline | PENDING | 1 週 + staging 1 週 | 與 2 平行 | **高** |
| **4** flow INDEX.md 自動生成 | PENDING | 0.5 週 | 需 Phase 2 完 | 低 |

**總工期**：2-3 週（1 名工程師全職）；或 1.5-2 週（2 名平行）。

---

## 1.0 Phase 0 — 文件治理基底（0.5 天）

### 1.1 ADR-0023（本決策）
- **檔案**：`docs/1-decisions/ADR-0023-tactical-refactor-2026-q2.md`
- **依賴**：無
- **驗收**：merge 後成為 5 個 Phase 的共同錨點

### 1.2 ADR-0024 預占（Phase 3 才寫內容）
- **檔案**：`docs/1-decisions/ADR-0024-harness-declarative-pipeline.md`
- **依賴**：Phase 3.1
- **本階段動作**：僅在 ADR-0023 提及；不預留占位檔（編號於 Phase 3 自然推進）

### 1.3 本 WBS
- **檔案**：`docs/4-exploration/wbs-2026-q2-tactical-refactor.md`（本檔）
- **依賴**：ADR-0023
- **驗收**：列出 5 Phase 的 PR 拆解與相依關係

### 1.4 CHANGELOG.md
- **檔案**：`CHANGELOG.md`（repo root，新建）
- **依賴**：無
- **格式**：[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) v1.1
- **本階段內容**：開新章節 `## [Unreleased] - 2026-Q2 Tactical Refactor`，引用 ADR-0023

**PR**: `docs(adr): ADR-0023 — 2026 Q2 戰術級重構計畫 + WBS-Q2 + CHANGELOG`

---

## 2.0 Phase 1.1 — 頂層雜訊清理（1 天）

### 2.1 檔案歸位

| 檔案 | 動作 | 影響 |
|---|---|---|
| `CLAUDE_TEMPLATE.md` | `git mv → .claude/CLAUDE_TEMPLATE.md` | 改 `.claude/settings.local.json` 的 SessionStart hook 引用 |
| `report/` | 加入 `.gitignore`（若仍有檔案則移至 `.dev-logs/report/`） | runtime artifact，零代碼引用 |
| `web_design_spec_prompt_pipeline/` | **保持原狀**（Q1 拍板） | 僅在 `project-structure.md` 註記 legacy |

### 2.2 `api/data/` → `api/storage/` 改名

- **動作**：`git mv api/data api/storage`
- **同步更新清單**：
  - `agent/Dockerfile`、`api/Dockerfile`：volume 引用
  - `docker-compose.mock.yml`：volume mount
  - `scripts/deploy/agent.sh`、`scripts/deploy/api.sh`：Cloud Run volume / GCS bucket 配置
  - `api/main.py` 或相關 router：`STATIC_FILES_DIR` 環境變數
  - `CLAUDE.md`：架構章節敘述
  - `docs/5-views/project-structure.md`：手動 sync
- **驗收**：
  - `grep -rn "api/data" --include="*.py" --include="*.sh" --include="*.yml" --include="*.toml"` 無殘留
  - `./scripts/deploy/api.sh --build-only` 通過

**PR**: `refactor(api): rename api/data → api/storage + repo root cleanup`

---

## 3.0 Phase 1.2 — Tier 5 自動生成器（1 天）

### 3.1 修 `project-structure.md` bug
- **檔案**：`docs/5-views/project-structure.md`
- **問題**：第 29-30 行兩條 `docs/` 重複
- **動作**：移除多餘行；確認 legacy docs 路徑已不存在

### 3.2 新增 generator script
- **檔案**：`scripts/ci/regen-project-structure.sh`（新增）
- **邏輯**：
  - `tree -L 2 --dirsfirst -I '.venv|node_modules|__pycache__|.git|.next|.dev-logs' agent/ api/ data/ web/ SQL/ scripts/`
  - 計算 Python/TypeScript file count + page.tsx count
  - sed 注入到 `project-structure.md` 對應區塊
  - 更新 frontmatter `last_regenerated` 與 `generator` 欄位

### 3.3 Makefile + CI 排程
- **Makefile target**：`make docs-regen`
- **CI workflow**：`.github/workflows/regen-docs.yml`
  - 觸發：weekly cron + manual dispatch
  - 動作：跑 generator → 若 diff 則開 PR

### 3.4 驗收
- `make docs-regen` 跑一次，diff 應只動 statistics + tree 區塊
- `./scripts/ci/check-operationid-orphans.sh` 通過

**PR**: `feat(docs): auto-regen project-structure.md (Tier 5)`

---

## 4.0 Phase 2 — web/src/ API 整合層（1 週）

### 4.1 設計原則
- **不動** `web/src/lib/api.ts`（raw HTTP client，已成熟）
- **不動** `web/src/components/`
- **新增** `web/src/api/` 與 `web/src/hooks/` 兩層

### 4.2 Phase 2.1 — 骨架 + pilot（1 PR）
- **檔案**：
  - `web/src/api/index.ts`
  - `web/src/api/work-orders.ts`
- **動作**：把 `web/src/app/work-orders/**/*.tsx` 中的 `api.get(...)` / `api.patch(...)` 抽成 named functions
- **驗收**：lint + build 通過；手動測 work-orders 列表頁

**PR**: `refactor(web): introduce src/api layer with work-orders pilot`

### 4.3 Phase 2.2 — SWR hook（1 PR）
- **依賴**：Phase 2.1 merge
- **動作**：
  - `npm install swr`
  - `web/src/hooks/useWorkOrders.ts`
  - 改寫 `work-orders/page.tsx` 改用 hook
- **驗收**：同頁多 component 共享 cache（不重複 fetch）

**PR**: `feat(web): add useWorkOrders hook with SWR`

### 4.4 Phase 2.3 — 漸進遷移其他 domains（7 PR）

依頁面流量/活躍度排序，每 domain 1 PR：

| # | Domain | 大致 PR 工作量 |
|---|--------|----------------|
| 1 | `conversations` | 0.5 天 |
| 2 | `problem-cards` | 0.5 天 |
| 3 | `dispatch` + `dispatch-queue` | 1 天 |
| 4 | `technicians` | 0.5 天 |
| 5 | `accounting/{invoices,vouchers,revenue}` | 1 天 |
| 6 | `admin/{refunds,disputes,warranty-claims,inventory}` | 1 天 |
| 7 | `knowledge-base/{cases,manuals,sop-drafts,family-reviews}` | 1 天 |

**驗收**（每 PR）：對應頁面手動測試通過；`web/src/components/<domain>/` 內無 `import { api }` 殘留。

---

## 5.0 Phase 3 — harness declarative pipeline（1 週 + staging 1 週）

> **最大風險點**。需 quality_check + evals 雙重把關 + staging 1 週驗證。

### 5.1 Phase 3.1 — Scaffolding（dark launch，1 PR）
- **檔案**：
  - `agent/harness/pipeline.py`（`HarnessLayer` Protocol + `Pipeline` class）
  - `agent/harness/context.py`（`HarnessContext` dataclass）
  - `docs/1-decisions/ADR-0024-harness-declarative-pipeline.md`
- **動作**：不改 `orchestrator.py` 行為；feature flag `enable_declarative_pipeline=false`
- **驗收**：`quality_check` + CLI `python main.py` 行為與重構前一致

**PR**: `feat(harness): introduce declarative pipeline scaffolding (dark launch)`

### 5.2 Phase 3.2 — 3 Layer Pilot（1 PR）
- **目標 layer**：`safety_gate`, `skills_prefix`, `agent_audit`（風險最低）
- **動作**：每個 layer 補 `apply(ctx)` 函式；orchestrator 對這 3 層改走 `Pipeline.run_layer(name, ctx)`
- **Fallback**：保留 `USE_PIPELINE_FOR=safety_gate,skills_prefix,agent_audit` env var
- **驗收**：`agent/evals/` golden set diff=0；`quality_check` 全綠

**PR**: `refactor(harness): migrate safety_gate/skills_prefix/agent_audit to pipeline`

### 5.3 Phase 3.3 — 全面遷移（1 PR + staging 1 週）
- **動作**：
  - 剩 6 層全部走 pipeline
  - 移除 `USE_PIPELINE_FOR` 與舊呼叫路徑
  - 更新 `docs/1-decisions/module-boundary/agent.md` 與 `CLAUDE.md` H 表格（補 config key 欄）
- **驗收**：
  - PR 通過 → merge 到 dev 分支
  - **dev 分支跑 quality_check + evals 連續 7 天，零退化**
  - 7 天後才合 main

**PR**: `refactor(harness): complete declarative pipeline migration`

---

## 6.0 Phase 4 — flow INDEX.md 自動生成（0.5 週）

### 6.1 依賴
- Phase 2 完成（需 web routes metadata）
- Phase 3 不強相依

### 6.2 動作
- **檔案**：
  - `docs/2-contracts/flows/INDEX.md`（新增）
  - `scripts/ci/regen-flow-index.sh`（新增）
  - `.github/workflows/flow-index-sync.yml`（新增）
- **邏輯**：
  - 解析 BF-*/SF-*.md frontmatter
  - 對照 `docs/2-contracts/api/openapi.yaml` operationId + tags
  - 對照 `web/src/app/**/page.tsx` metadata
  - 產出表格：每個 BF/SF → operationId 清單 + 前端頁面路由 + 後端 router 檔案 + 相關 FR-xxxx

### 6.3 CI Gate
- 每次 BF/SF .md 改動觸發 regen
- diff 不為零則 CI fail（強制開發者跑 `make flow-index-regen` 後重提）

### 6.4 驗收
- 隨機抽 3 個 SF，從 INDEX.md 應能一鍵跳到對應 OpenAPI / 前端頁面 / 後端 router

**PR**: `feat(docs): auto-generated flow-to-api-to-page index`

---

## 7.0 風險登錄與緩解

| 風險 | 機率 | 影響 | 緩解 |
|---|---|---|---|
| Phase 1.1 `api/data/` 改名漏改 deploy 腳本 | 中 | 中（部署失敗）| 改名前 `grep -rn "api/data"` 完整掃描；改完跑 `--build-only` 驗證 |
| Phase 2 漸進遷移期間新舊 API 風格並存 | 高 | 低（短期）| 在 PR 描述明確標示「遷移進行中」；Phase 2.3 完成後出 cleanup PR |
| Phase 3.2 layer apply(ctx) 行為偏差 | 中 | **高**（agent 回覆品質下降） | golden set diff=0 + quality_check 全綠才 merge；`USE_PIPELINE_FOR` env var 可即時回退 |
| Phase 3.3 staging 7 天內出現退化 | 中 | **高** | staging 監控 LLM cost / response time / 錯誤率三指標；任一退化立即 revert 並回到 Phase 3.2 狀態 |
| Phase 4 INDEX.md 自動生成漏 Flow / 錯誤對映 | 低 | 中 | 隨機抽 3 個 SF 人工驗證；CI gate 採 warning 而非 error 跑首週 |
| 既有 sync hook（dispatch-engine.md 等）持續干擾 working tree | 高 | 低 | 每次 commit 前 `git status` 精準 stage，不用 `git add .` |

---

## 8.0 驗收條件（5 Phase 全部完成）

- [ ] ADR-0023 + ADR-0024 已 merge
- [ ] `web/src/api/` 覆蓋率 ≥ 80%（依 domain 計）
- [ ] `web/src/hooks/` 至少 5 個 domain hook
- [ ] `agent/harness/pipeline.py` 已全面取代 module-level wiring；orchestrator 中無 `import harness.{layer}` 硬編碼
- [ ] `docs/5-views/project-structure.md` 由 `make docs-regen` 自動產出
- [ ] `docs/2-contracts/flows/INDEX.md` 存在且 CI gate 啟用
- [ ] 頂層只剩 4 大模組 + 標準工具目錄；無 `CLAUDE_TEMPLATE.md`、`report/` 殘留
- [ ] `api/data/` 已完全改名為 `api/storage/`；無殘留引用
- [ ] CHANGELOG.md 完整紀錄 5 Phase 變更

---

## 9.0 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-11 | 初版 — 對應 ADR-0023 拍板 |
