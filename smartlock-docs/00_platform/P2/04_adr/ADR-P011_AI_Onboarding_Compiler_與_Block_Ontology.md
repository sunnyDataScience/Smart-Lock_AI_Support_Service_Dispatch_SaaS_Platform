# ADR-P011: AI Onboarding Compiler + Block Ontology（流程自動化護城河）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（target-state 理想態 v2）· 北極星 |
| 日期 | 2026-07-07 |
| 決策者 | 業主 + 架構師 |
| 層級 | 平台級（Platform）· 策略護城河 |
| 關聯 | [[ADR-P010]]（編譯目標=flow DSL）· [[ADR-P001]]（孿生 HITL 模式）· `06_platformization_strategy` §9 |

## 1. 背景與問題

平台化的**護城河**不是「有個拖拉編輯器」（n8n / ServiceTitan 都有），而是三層複利：(1) 積木庫隨每次產業落地累積、(2) AI 把客戶 tacit 流程編譯成可執行 flow、(3) 累積的 flow + 積木**編碼各產業商業邏輯**。問題：如何把這三層變成可實作的能力與治理機制？

## 2. 考量的選項

- **A：純人工 onboarding**（顧問手刻流程）— 慢、不累積、無護城河。
- **B：通用 workflow builder**（如 n8n）— 有編輯器無藍領本體論、無 AI 編譯、無累積。
- **C：AI Onboarding Compiler + 治理化 Block Ontology** — 客戶流程 AI 編譯成 DSL、積木庫飛輪、HITL 審核。

## 3. 決策

採 **選項 C**，三個機制：

### 3.1 AI Onboarding Compiler
- **輸入**：客戶 tacit 流程（SOP 文件 / 訪談 / 舊系統匯出 / 對話）。
- **編譯**：AI 對映到 **Block Ontology（既有積木詞彙）** → 產出 **draft flow DSL**（[[ADR-P010]]）+ **標記缺口**（需新積木/自訂節點的步驟）。
- **輸出**：draft flow → 拖拉 UI 呈現。

### 3.2 Block Ontology（積木本體論，飛輪）
- 積木 = 型別節點 + 契約（[[ADR-P010]] §3.3）。
- 每落地一產業 → 發現新積木 → **進庫（版本化 + 治理 + 向後相容）**。
- 積木庫 = 累積的藍領營運本體論；越後面產業越多是重組 → onboarding 越快。

### 3.3 HITL 審核（孿生 knowledge-refinery）
- **draft → 人審 → 匯入呈現**——與 [[ADR-P001]] 知識精煉**同一模式、共用審核 UI 骨架**（一煉知識、一煉流程）。
- 碰**金流 / 派工 / 同意書**的流程，AI 編出**必過人審**才上線，**不盲匯入**。

## 4. 後果

**正面**：onboarding 從「顧問手刻」→「AI 編譯 + 人審」數量級加速；護城河 = 藍領積木本體論 × AI 編譯器 × 累積商業邏輯（轉換成本 + 資料護城河）；與 refinery 共用骨架，架構自洽。
**負面/風險**：
- **DSL-first 前置**：本能力**疊在穩定 DSL 上**（[[ADR-P010]]），DSL 未穩不能先做。
- **飛輪冷啟動**：頭 2-3 產業積木**手工建**、AI 命中率低——須誠實面對，勿以「AI 一鍵匯入」對外承諾過早。
- **安全**：AI 編出的商業流程有錯/不安全風險 → HITL + 匯入驗證為硬 gate。
**影響範圍**：新增 AI 編譯服務（複用 refinery 服務/UI 骨架，屬 License 附加）；Block Ontology 治理（版本/相容/棄用）。
**重新評估觸發**：積木庫成熟後評估「半自動匯入」（低風險流程免全人審）。

## 5. 執行計畫（依賴 [[ADR-P010]] DSL 先穩）
1. **Phase 0**：DSL + 積木契約 + 引擎（[[ADR-P010]] Phase 1）。
2. **Phase 1**：Block Ontology v0（locksmith 手工積木）+ 治理（版本/registry）。
3. **Phase 2**：AI Compiler MVP（客戶 SOP → draft DSL + 缺口標記）+ HITL 審核 UI（複用 refinery）。
4. **Phase 3**：飛輪運轉——第 2、3 產業回饋積木庫，量測 AI 命中率提升。

## 6. 選用影響區段
- **架構**：AI 編譯服務（refinery 孿生）+ Block Ontology 治理。
- **安全**：HITL + 匯入驗證硬 gate（金流/派工/同意書）。
- **商業**：護城河 = 累積本體論 + 轉換成本；License 附加能力。
- **依賴**：嚴格後於 [[ADR-P010]] DSL 穩定。
