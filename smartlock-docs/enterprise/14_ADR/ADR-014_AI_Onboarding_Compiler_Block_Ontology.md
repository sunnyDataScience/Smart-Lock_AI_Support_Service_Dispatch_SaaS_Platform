---
title: "ADR-014: AI Onboarding Compiler + Block Ontology（流程自動化護城河）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P011_AI_Onboarding_Compiler_與_Block_Ontology.md
---

# ADR-014: AI Onboarding Compiler + Block Ontology（流程自動化護城河）

| 欄位 | 內容 |
|---|---|
| 狀態 | 規劃中（北極星）|
| 層級 | 平台級 · 策略護城河 |
| 關聯 ADR | [ADR-013](./ADR-013_Flow-as-Blocks宣告式DSL.md)（編譯目標 = flow DSL，硬前置）· [ADR-018](./ADR-018_知識精煉獨立服務.md)（孿生 HITL 模式）· [ADR-001](./ADR-001_平台核心與領域配置分層.md) |

## Context（背景與問題）

平台化的護城河不是「有個拖拉編輯器」（n8n / ServiceTitan 都有），而是三層複利：(1) 積木庫隨每次產業落地累積、(2) AI 把客戶 tacit 流程編譯成可執行 flow、(3) 累積的 flow + 積木**編碼各產業商業邏輯**。問題：如何把這三層變成可實作的能力與治理機制？

## Decision（決策）

三個機制：

### AI Onboarding Compiler
- **輸入**：客戶 tacit 流程（SOP 文件 / 訪談 / 舊系統匯出 / 對話）。
- **編譯**：AI 對映到 **Block Ontology（既有積木詞彙）** → 產出 **draft flow DSL**（[ADR-013](./ADR-013_Flow-as-Blocks宣告式DSL.md)）+ **標記缺口**（需新積木 / 自訂節點的步驟）。
- **輸出**：draft flow → 拖拉 UI 呈現。

### Block Ontology（積木本體論，飛輪）
- 積木 = 型別節點 + 契約（[ADR-013](./ADR-013_Flow-as-Blocks宣告式DSL.md)）。
- 每落地一產業 → 發現新積木 → **進庫（版本化 + 治理 + 向後相容）**。
- 積木庫 = 累積的藍領營運本體論；越後面的產業越多是重組 → onboarding 越快。

### HITL 審核（孿生 knowledge-refinery）
- **draft → 人審 → 匯入呈現**——與 [ADR-018](./ADR-018_知識精煉獨立服務.md) 同一模式、共用審核 UI 骨架（一煉知識、一煉流程）。
- 碰**金流 / 派工 / 同意書**的流程，AI 編出**必過人審**才上線，不盲匯入。

## Alternatives（考量的選項）

- **A：純人工 onboarding（顧問手刻流程）** — 慢、不累積、無護城河。
- **B：通用 workflow builder（如 n8n）** — 有編輯器無藍領本體論、無 AI 編譯、無累積。
- **C：AI Compiler + 治理化 Block Ontology（採用）** — AI 編譯 + 積木飛輪 + HITL。

## Consequences（後果）

**正面**：onboarding 從「顧問手刻」→「AI 編譯 + 人審」數量級加速；護城河 = 藍領積木本體論 × AI 編譯器 × 累積商業邏輯（轉換成本 + 資料護城河）；與 refinery 共用骨架，架構自洽。
**風險**：
- **DSL-first 硬前置**：本能力疊在穩定 DSL 上，DSL 未穩不能先做。
- **飛輪冷啟動誠實面**：頭 2-3 個產業積木**手工建**、AI 命中率低——不得以「AI 一鍵匯入」對外過早承諾。
- **安全**：AI 編出的商業流程有錯 / 不安全風險 → HITL + 匯入驗證為硬 gate。
**影響範圍**：新增 AI 編譯服務（複用 refinery 服務 / UI 骨架，屬 License 附加系統）；Block Ontology 治理（版本 / 相容 / 棄用）。
**重評觸發**：積木庫成熟後評估「半自動匯入」（低風險流程免全人審）。

## Status 附註

- 🔜 全部規劃中，依賴序：Phase 0 = [ADR-013](./ADR-013_Flow-as-Blocks宣告式DSL.md) DSL 穩定 → Phase 1 Block Ontology v0（locksmith 手工積木 + registry）→ Phase 2 AI Compiler MVP（SOP → draft DSL + 缺口標記）+ HITL 審核 UI → Phase 3 飛輪運轉（第 2、3 產業回饋，量測 AI 命中率）。
