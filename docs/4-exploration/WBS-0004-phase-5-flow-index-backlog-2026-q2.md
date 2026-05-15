# Phase 5' Backlog — Flow INDEX 兩階段（2026 Q2）

**對應 ADR：** [ADR-0024](../1-decisions/ADR-0024-tier1-refactor-revised.md) §3 S5
**對應 WBS：** [wbs-2026-q2-tactical-refactor.md](./wbs-2026-q2-tactical-refactor.md) §6.0
**狀態：** **BACKLOG / DEFER**（2026-05-12 ROI 重評估後 defer；明確觸發條件見 §D）
**建立日：** 2026-05-12

---

## 1. 背景

Phase 3.3 backlog 全部收尾後（2026-05-12，PR #75-#84），依 ADR-0024 §3 S5 進入 Phase 5' 重估時點：

> ADR-0024 §3 S5：「Flow INDEX 進入 backlog。Phase 1-4 完成後重估 ROI，視 V3 多通道擴展時程決定是否啟動。若 V3 延後超過 3 個月 → 從 backlog 移除（避免 over-optimization）」

本文件記錄 2026-05-12 的重估結果與 defer 決策。

## 2. 範圍回顧

Phase 5' 拆兩階段：

| 子階段 | 動作 | 工作量 |
|---|---|---|
| **5.1** | 補 25 BF + 25 SF + 25 FR (合計 ~75 檔) 的 frontmatter 加 `related_apis: []` 與 `related_pages: []` 欄位 | 3-5 天（手工）|
| **5.2** | `scripts/ci/regen-flow-index.sh` 自動聚合 frontmatter 產出 `docs/2-contracts/flows/INDEX.md` + CI gate (`.github/workflows/flow-index-sync.yml`) | 0.5 天 |

預期產出：
- `docs/2-contracts/flows/INDEX.md` — 機讀對照表（Flow ↔ OpenAPI operationId ↔ web route ↔ FR ID）
- 每次 BF/SF/FR 變動觸發 CI re-gen；diff 不為零則 fail

---

## 3. ROI 重評估（2026-05-12）

### 收益面

| 維度 | 評估 |
|---|---|
| **新人 onboarding** | 中等正面 — 新人從 Flow INDEX 一鍵跳到對應 API + 頁面，省去翻 3 個目錄 |
| **跨模組整合 debug** | 低正面 — 目前未發現「找不到 Flow ↔ API 對應」造成的具體 bug |
| **V3 多通道鋪路** | 中等正面 — 新 channel adapter 可一眼看到 cross-reference；但 V3 時程不明確 |
| **AI agent / IDE auto-complete** | 中等正面 — Claude Code 等工具可從結構化 frontmatter 推 cross-reference |

### 成本面

| 維度 | 評估 |
|---|---|
| **5.1 初次補 75 檔 frontmatter** | 3-5 天工時，純手工（非可自動化），中等心智成本 |
| **持續維護負擔** | **高** — git log 顯示 BF/SF/FR 高頻變動（feat(modules)、feat(test-cases)、feat(traceability) 等 weekly 級新增），每次都要補欄位 + 跑 generator + 過 CI gate |
| **CI gate 假警報風險** | 中等 — frontmatter 漏 sync 會 fail CI，可能成為新型「卡進度」噪音 |
| **與既有 traceability-matrix.md 重疊** | **HIGH** — `docs/5-views/VIEW-0005-traceability-matrix.md` 已含 BDD scenario / FR / TC trace；Flow INDEX 與其資料維度重疊 |

### 訊號

| 訊號 | 狀態 |
|---|---|
| V3 多通道時程 | **不明確**（無對外承諾日期） |
| 新人 onboarding 痛點 | **未量化**（沒有具體報告） |
| 跨模組整合 bug 紀錄 | **零**（grep `issues/PRs` 無相關 incident） |
| BF/SF/FR 變動頻率 | **高**（weekly+，會放大維護成本） |
| 既有 traceability-matrix.md 用量 | **未量化**（不知有沒有人在用） |

### 結論：**DEFER**

**理由**：成本面（持續維護 + traceability-matrix 重疊）顯著高於收益面（V3 時程不明 + 新人痛點未量化）。當下啟動 = 預先投資 8 天工時 + 高維護成本，換取「未來可能用得到」的索引；不對齊 Linus「實用主義」原則（解決真實問題，不解決臆想問題）。

---

## 4. 觸發條件（量化、可審計）

依 ADR-0024 「重新評估觸發」精神 + Phase 3.3 backlog §F pattern，本 backlog 明確列以下**任一條件觸發**重啟 Phase 5'：

| 編號 | 條件 | 量化指標 | 對應動作 |
|---|---|---|---|
| **T1** | V3 多通道擴展啟動 | 開出對應 V3 ADR（如 ADR-0030+ 拍板 SMS/WhatsApp/Email channel adapter 設計） | 啟動 5.1 + 5.2 完整流程 |
| **T2** | 跨模組整合 incident 累積 | 6 個月內 ≥ 3 次「找不到 Flow ↔ API 對應」相關 PR comment / issue（grep 標籤 `cross-ref-confusion`） | 啟動 5.1（暫不做 5.2） |
| **T3** | 新人 onboarding 量化痛點 | 新成員加入後 30 天內 PR comment 出現「不知道某 Flow 對應哪支 API」≥ 5 次 | 啟動 5.1 frontmatter 補完，5.2 視情況 |
| **T4** | Flow ID 系統大改 | 出現 BF/SF/FR 命名重組或大規模新增（單月 ≥ 20 個新 ID） | 啟動 5.2 generator（先有自動化，再補欄位） |

**移除條件**：

| 編號 | 條件 | 量化指標 | 動作 |
|---|---|---|---|
| **R1** | 12 個月閒置 | 2027-05-12 仍無 T1-T4 任一觸發 | 從 backlog 移除；ADR-0024 §3 S5 補 superseded 紀錄 |
| **R2** | 替代方案出現 | `traceability-matrix.md` 經過擴展已涵蓋 BF ↔ API ↔ page 三維 cross-reference | 從 backlog 移除；改在 traceability-matrix §F 補 cross-link |

---

## 5. 若啟動：5.1 / 5.2 具體執行步驟

### 5.1 frontmatter 補欄位（3-5 天，手工）

**目標檔案範圍**（依 Flow ID convention）：
- `docs/2-contracts/flows/business/BF-*.md` (~5 個)
- `docs/2-contracts/flows/sub/SF-*.md` (~23 個)
- `docs/2-contracts/functional-requirements/FR-*.md` (~25 個)

**新增 frontmatter 欄位**：

```yaml
---
id: BF-0001
# ... existing fields
related_apis:
  - acceptWorkOrder          # OpenAPI operationId
  - rejectWorkOrder
  - completeWorkOrder
related_pages:
  - /work-orders             # web route
  - /work-orders/[id]
related_frs:                 # 如為 BF/SF；FR 自身不需 related_frs
  - FR-0007
  - FR-0008
---
```

**進度追蹤**：依 Phase 3.3 batch 模式，按 domain 拆 PR：
- Batch 1: BF business (5 個檔)
- Batch 2: SF-WO* (~13 個)
- Batch 3: SF-DSP*, SF-G* (~10 個)
- Batch 4: FR-* (~25 個)

### 5.2 自動生成器（0.5 天）

**新增**：
- `scripts/ci/regen-flow-index.sh` — 解析 frontmatter + 對照 openapi.yaml operationId + 對照 web/src/app/**/page.tsx metadata
- `.github/workflows/flow-index-sync.yml` — 每次 BF/SF/FR 變動觸發 regen；diff 不為零則 CI fail
- `docs/2-contracts/flows/INDEX.md` — 自動產出，標 `<!-- AUTO-GENERATED; DO NOT EDIT -->`

**ADR-0026 預留**：執行 5.1 + 5.2 時建議開新 ADR 紀錄「為何重啟 Phase 5'」+ 對應觸發條件。

---

## 6. 不在範圍

| 項目 | 理由 |
|---|---|
| ❌ 同步補 PR / commit / git log 引用 BF/SF/FR ID 的反向索引 | 已由 git 原生 grep / GitHub PR search 涵蓋；不需新建 |
| ❌ Flow ID 命名空間重組 | ADR-0024 §6 明訂不在範圍（數千個引用） |
| ❌ traceability-matrix.md 整合至 Flow INDEX | 兩者語意不同（前者 BDD/FR/TC，後者 Flow/API/Page）；保持獨立 |
| ❌ AsyncAPI / WebSocket event 索引 | 待 V3 多通道擴展時再評估（與 5.1 同 timing） |

---

## 7. 變更紀錄

| 日期 | 內容 |
| :--- | :--- |
| 2026-05-12 | 初版 — ADR-0024 §3 S5 ROI 重評估後 defer；列 T1-T4 啟動條件 + R1-R2 移除條件 |
