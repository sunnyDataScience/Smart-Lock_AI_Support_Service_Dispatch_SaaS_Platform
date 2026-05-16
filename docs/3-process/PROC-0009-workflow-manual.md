---
id: PROC-0009
title: 開發流程總覽手冊 (Development Workflow Cookbook)
tier: 3
status: active
owner: Tech Lead
last_updated: 2026-05-16
---

# 開發流程總覽手冊 (Development Workflow Cookbook)

# 電子鎖智能客服與派工平台 — SmartLock-SaaS

---

**文件版本 (Document Version):** `v2.0`
**最後更新 (Last Updated):** `2026-04-04`
**主要作者 (Lead Author):** `開發團隊`
**狀態 (Status):** `活躍 (Active)`

---

## 目錄 (Table of Contents)

- [I. 核心理念：從商業價值到高品質程式碼](#i-核心理念從商業價值到高品質程式碼)
- [II. 開發階段與文件產出](#ii-開發階段與文件產出)
  - [第一階段：規劃 (Planning) - 定義「為何」與「什麼」](#第一階段規劃-planning---定義為何與什麼)
  - [第二階段：設計 (Design) - 定義「如何」的藍圖](#第二階段設計-design---定義如何的藍圖)
  - [第三階段：開發 (Development) - 精確實現](#第三階段開發-development---精確實現)
  - [第四階段：品質與部署 (Quality & Deployment)](#第四階段品質與部署-quality--deployment)
- [III. 支援文件](#iii-支援文件)
- [IV. 文件成熟度總覽](#iv-文件成熟度總覽)

---

## I. 核心理念：從商業價值到高品質程式碼

**目的**: 本手冊旨在提供一個頂層指導，說明整個開發流程的各個階段、目標，並作為導航中心，連結到所有相關的文件範本。

本開發流程旨在建立一個從商業需求到高品質程式碼的完整、可追溯的鏈路。我們融合 BDD (行為驅動開發)、DDD (領域驅動設計)、Clean Architecture (潔淨架構) 與 TDD (測試驅動開發)，形成一套以「規格」為驅動、以「測試」為驗證的現代軟體開發模型。

### Software 3.0 範式

本專案採用 Software 3.0 開發範式，核心原則如下：

- **知識即資料 (Knowledge-as-Data)**: 領域知識以結構化 JSON/TOML 格式儲存，作為系統的 ground truth，而非硬編碼於程式邏輯中。
- **推理委派 LLM (Reasoning-by-LLM)**: 複雜的診斷推理、意圖辨識、自然語言生成等任務委派給 LLM prompt，而非以 Python rule-based 程式碼實作。
- **8-Layer Harness Framework**: 系統以 8 層治理框架（L0 Config ~ L7 Observability）包覆 LLM 推理核心，確保可控性、可追溯性與安全性。

**推演的第一性原理:**

1.  **從「為何」到「什麼」，再到「如何」**:
    *   **為何 (Why)**: 革新電子鎖售後服務，將資深技師的專家知識系統化、可傳承，消除從報修到結案的所有人工瓶頸。
    *   **什麼 (What)**: V1.0 AI 智能客服系統（LINE Bot + ProblemCard + 三層解決機制 + 自進化知識庫），V2.0 技師派工與帳務平台（智慧媒合派工 + 計價引擎 + 帳務系統）。
    *   **如何 (How)**: FastAPI + PostgreSQL/pgvector + LangChain/LangGraph + Gemini 2.5 Flash + LINE Bot SDK，以 Clean Architecture + DDD 分層實現，搭配 8-Layer Harness Framework 治理 AI 推理層。

2.  **品質內建 (Quality Built-in)**: 我們不將測試視為事後檢查，而是將其融入開發的每一步。BDD 情境定義允收標準、模組規格定義函式契約、TDD 確保每一行程式碼都被測試覆蓋，從根本上減少錯誤。

3.  **AI 輔助就緒 (AI-Assistant Ready)**: 流程中的每一份文件都旨在產生精確、無歧義的「上下文」，為大型語言模型 (LLM) 輔助開發提供必要的「護欄」。

---

## II. 開發階段與文件產出

本流程分為四個主要階段，每個階段都會產出關鍵文件，環環相扣，共同構成專案的完整藍圖。

### **第一階段：規劃 (Planning) - 定義「為何」與「什麼」**

**目標**: 確保開發方向從一開始就與商業價值和使用者需求對齊。

1.  **[專案簡報與產品需求 (PRD)](./02_project_brief_and_prd.md)** `已批准 (Approved)`
    *   **目的**: 定義專案的「為何」與「為誰」，設定最高層次的目標和邊界。
    *   **產出**: 完整的 PRD 文件，包含商業目標（4 大 KPI：AI 自助解決率 >= 60%、首次回應時間 < 5 秒、知識庫每月自動新增 >= 10 條 SOP、派工接單率 >= 90%）、31 條使用者故事（US-001 ~ US-031）、成功指標及範圍限制。
    *   **關鍵產物**: 五類利害關係人定義（甲方、乙方、消費者、技師、總部管理員）、V1.0/V2.0 交付時程（W1-W17 / W18-W31）。

2.  **[行為驅動情境 (BDD Scenarios)](./03_behavior_driven_development.md)** `活躍 (Active)`
    *   **目的**: 將 PRD 中的使用者故事轉化為精確、無歧義的 Gherkin 規格，作為連接業務與技術的橋樑。
    *   **產出**: 完整的 BDD Feature 文件，涵蓋 V1.0 六大 Feature（LINE Bot 客服對話、ProblemCard 分診、三層解決機制、自進化知識庫、管理後台、安全防護）與 V2.0 六大 Feature（師傅工作台、智慧派工引擎、標準化定價引擎、自動化會計系統、管理後台 V2.0、V1<->V2 資料串接）。
    *   **通用語言 (Ubiquitous Language)**: ProblemCard（問題卡）、Three-Layer Resolution Engine（三層解決機制）、SOP Draft（SOP 草稿）、Pricing Engine（定價引擎）、Dispatch Matching（派工匹配）、Case Pool（案件池）、Completion Report（完工回報）。

### **第二階段：設計 (Design) - 定義「如何」的藍圖**

**目標**: 將業務需求轉化為穩固、可擴展的技術藍圖，避免系統演變成難以維護的「大泥球」。

3.  **[架構與設計文檔 (SAD & SDD)](./05_architecture_and_design_document.md)** `已批准 (Approved)`
    *   **目的**: 建立系統的結構（架構）並填充具體的實現細節（設計）。
    *   **產出**: 整合性設計文檔，包含：
        *   **C4 模型**: L1 系統情境圖、L2 容器圖、L3 組件圖（四大組件：LINE Bot Gateway、AI Service Layer、Admin API、Data Layer）
        *   **DDD 戰略設計**: 六大 Bounded Context（conversation、problem_card、knowledge_base、dispatch、pricing、accounting）
        *   **Clean Architecture 分層**: 六層堆疊（UI -> API Gateway -> AI Service -> Business Domain -> Data Access -> Infrastructure）
        *   **數據架構**: PostgreSQL Schema（`SQL/Schema.sql`）、pgvector HNSW 索引策略（768 維、m=16、ef_construction=64）
        *   **部署架構**: 三環境策略（Dev / Staging / Production）、Docker Compose 容器編排
    *   **連結子文件**:
        *   **[架構決策記錄 (ADR)](../adrs/)**: 6 份已決策 ADR
            - ADR-001: 後端框架選型 -> FastAPI
            - ADR-002: 資料庫選型 -> PostgreSQL 16 + pgvector 0.7
            - ADR-003: LLM 整合框架 -> LangChain 0.3 + Google Gemini
            - ADR-004: LINE Bot 架構 -> line-bot-sdk-python 3 + Webhook
            - ADR-005: 前端框架選型 (V2.0) -> Next.js 14 + shadcn/ui
            - ADR-006: LLM 模型選擇策略 -> Gemini 2.5 Flash 為主力推理模型
        *   **[API 設計規格](./06_api_design_specification.md)** `已批准 (Approved)`: RESTful API 全端點規範，涵蓋 V1.0（認證、Webhook、對話、ProblemCard、案例庫、手冊管理、SOP 管理、儀表板）及 V2.0（派工、技師、報價、帳務）端點，含完整的 Request/Response Schema 定義。
        *   **[V2.0 系統設計規格](../system_design/specs/)** `活躍 (Active)`: 14 份 V2.0 設計規格文件，涵蓋 RBAC 動態權限、即時訊息、庫存管理、電子簽章、稽核日誌、B2B API、品牌資料 API、資料匯出、退款審批、保固糾紛、SLA 可用性、視覺處理、Agent 間訊息傳遞、護城河映射矩陣。
        *   **[Agent Harness 重構文件](../agent-harness-refactor/)** `活躍 (Active)`: 診斷智能架構（diagnostic-intelligence-architecture.md）、優化策略（optimization-strategy.md）、ProblemCard 規格（problem-card-spec.md）等，定義 8-Layer Harness Framework 的設計與演進路線。

4.  **[資料庫 Schema](../../SQL/Schema.sql)** `已定義 (Defined)`
    *   **目的**: 定義系統的完整數據模型。
    *   **產出**: PostgreSQL DDL，包含：
        *   **V1.0 核心 8 張表**: users、conversations、messages、problem_cards、manuals、manual_chunks、case_entries、sop_drafts
        *   **V2.0 擴充 14 張表**: 原有核心表演進加上 technicians、work_orders、price_rules、invoices、reconciliations、settlements 等，含完整索引策略與向量索引
        *   **[V2.0 Extensions](../../SQL/Schema_v2_extensions.sql)**: 6 張新表（roles、permissions、role_permissions、inventory_items、inventory_transactions、digital_signatures），支援 RBAC 動態權限、庫存管理與電子簽章

### **第三階段：開發 (Development) - 精確實現**

**目標**: 透過 TDD 和契約式設計，確保每一個程式碼單元都被精確、健壯地實現。

5.  **[模組規格與測試](./07_module_specification_and_tests.md)** `草稿 (Draft)`
    *   **目的**: 將高層次的 BDD 情境分解到具體的模組或類別層級，並使用契約式設計 (DbC) 來精確定義其職責邊界。
    *   **產出**: V1.0 五大核心模組規格，每個模組包含函式簽名、前置/後置條件、不變式、測試情境：
        - **模組 1: ConversationManager** -- 對話編排器，處理意圖辨識、NER、狀態機轉換
        - **模組 2: ProblemCardEngine** -- 問題卡生成與完整度評估
        - **模組 3: ThreeLayerResolver** -- 三層解決機制（L1 案例庫 -> L2 RAG -> L3 轉人工）
        - **模組 4: KnowledgeBaseManager** -- 案例庫搜尋與手冊匯入 Pipeline
        - **模組 5: SOPGenerator** -- SOP 自動生成與去重
    *   **V2.0 業務服務模組**: V2.0 業務邏輯已實作於 `agent/services/` 目錄，包含 16 個業務服務模組（audit、auth、brand、complaint、completion、consent、dispatch、dispute、export、finance、inventory、messaging、pricing、technician、warranty、work_order），涵蓋 GAP 分析中全部 30 項缺口。

6.  **[模組依賴關係分析](./09_file_dependencies.md)** `草稿 (Draft)`
    *   **目的**: 定義模組間的依賴方向與層級關係，確保依賴方向符合 Clean Architecture 原則（依賴朝內、永不反轉）。
    *   **產出**: 高層級模組依賴圖、關鍵依賴路徑分析、外部依賴管理策略。

7.  **[類別/組件關係文檔](./10_class_relationships.md)** `草稿 (Draft)`
    *   **目的**: 細化領域實體、值物件、聚合根之間的關係。
    *   **產出**: 領域模型類別圖，涵蓋 DDD 六大 Bounded Context 的實體關係。

### **第四階段：品質與部署 (Quality & Deployment)**

**目標**: 確保專案在交付前符合安全、隱私與生產環境的標準。

8.  **[綜合品質檢查清單](./13_security_and_readiness_checklists.md)** `使用中 (In Use)`
    *   **目的**: 在設計階段與部署前進行全面的安全、隱私和生產準備就緒審查。
    *   **產出**: 已完成的檢查清單，涵蓋七大領域：
        - A. 核心安全原則（最小權限、縱深防禦）
        - B. 數據生命週期安全與隱私
        - C. 應用程式安全（OWASP Top 10 對照）
        - D. 基礎設施與運維安全
        - E. 合規性
        - F. 審查結論與行動項
        - G. 生產準備就緒（可觀測性、可靠性、性能、可維護性）

9.  **[部署與運維指南](./14_deployment_and_operations_guide.md)** `草稿 (Draft)`
    *   **目的**: 提供從開發到上線的完整部署操作手冊。
    *   **產出**: 部署架構總覽（三環境策略、Docker Compose 拓撲）、CI/CD 流水線（`ci.yml` + `deploy.yml`）、部署檢查清單。

10. **[Code Review 與重構指南](./11_code_review_and_refactoring_guide.md)** `草稿 (Draft)`
    *   **目的**: 建立團隊統一的 Code Review 標準與重構模式。
    *   **產出**: Review Checklist、常見重構模式、品質閘門定義。

---

## III. 支援文件

以下文件不屬於特定階段，但在整個開發生命週期中提供持續支援：

*   **[專案結構指南](./08_project_structure_guide.md)** `活躍 (Active)`: 標準化的 Clean Architecture 目錄結構規範（按領域/功能組織，非按技術類型），確保 V1.0 -> V2.0 平滑過渡。
*   **[前端架構規範](./12_frontend_architecture_specification.md)** `草稿 (Draft)`: V2.0 Next.js 14 + shadcn/ui 前端開發規範。
*   **[前端信息架構](./17_frontend_information_architecture.md)** `草稿 (Draft)`: 前端頁面導航、用戶流程、信息層級設計。
*   **[文檔與維護指南](./15_documentation_and_maintenance_guide.md)** `草稿 (Draft)`: 文檔標準與維護流程定義。
*   **[系統架構總覽](./executive_architecture_overview.md)** `已完成 (Completed)`: 高階系統分層堆疊圖與資料流總覽，適用於利害關係人簡報。
*   **[WBS 開發計畫](./WBS_電子鎖智能平台.md)** `已定義 (Defined)`: 31 週工作分解結構，含 8 個 Phase、各工作包的交付物與負責方。
*   **[系統設計規格](../system_design/specs/)** `活躍 (Active)`: 14 份 V2.0 系統設計規格文件，涵蓋 RBAC、即時訊息、庫存管理、電子簽章、稽核日誌、B2B API、品牌資料、資料匯出、退款審批、保固糾紛、SLA、視覺處理、Agent 間訊息、護城河映射等。
*   **[Agent Harness 重構文件](../agent-harness-refactor/)** `活躍 (Active)`: 診斷智能架構、優化策略、ProblemCard 規格、GAP 分析、Graph Flow 重新設計、Harness 架構、遷移路線圖、WBS 開發計畫等，定義 8-Layer Harness Framework 的完整設計。
*   **[護城河映射矩陣](../system_design/specs/moat-mapping-matrix.md)** `已完成 (Completed)`: 投資人 5 項 vs 系統 10 項護城河映射，連結商業價值與技術實現。
*   **[領域知識資料](../data/)**:
    - `data/RAG/` -- RAG 知識庫原始資料
    - `data/transcript/` -- 領域專家訪談逐字稿（產品知識、故障排除、系統需求討論）

---

## IV. 文件成熟度總覽

| 階段 | 文件 | 狀態 | 文件路徑 |
|:-----|:-----|:-----|:---------|
| **規劃** | 專案簡報與 PRD | 已批准 | `docs/00-discover/E1--project-brief-and-prd.md` |
| **規劃** | BDD 情境 | 活躍 | `docs/_flows-bdd-test/v-model-right/E7--bdd-scenarios.md` |
| **設計** | 架構與設計文檔 | 已批准 | `docs/01-define/E3--architecture-and-design.md` |
| **設計** | ADR (6 份) | 已決策 | `docs/01-define/adrs/adr-001 ~ adr-006` |
| **設計** | API 設計規格 | 已批准 | `docs/02-design/E5--api-design-specification.md` |
| **設計** | 資料庫 Schema | 已定義 | `SQL/Schema.sql` |
| **設計** | 資料庫 Schema V2.0 Extensions | 已定義 | `SQL/Schema_v2_extensions.sql` |
| **設計** | V2.0 系統設計規格 (14 份) | 活躍 | `docs/02-design/specs/` |
| **設計** | Agent Harness 重構文件 | 活躍 | `docs/agent-harness-refactor/` |
| **設計** | 護城河映射矩陣 | 已完成 | `docs/00-discover/moat-mapping-matrix.md` |
| **開發** | 模組規格與測試 | 草稿 | `docs/_flows-bdd-test/v-model-left/E7x--module-spec-v1-core.md` |
| **開發** | V2.0 業務服務模組 (16 個) | 活躍 | `agent/services/` |
| **開發** | 模組依賴關係 | 草稿 | `docs/02-design/E6x--file-dependencies.md` |
| **開發** | 類別關係文檔 | 草稿 | `docs/02-design/E6x--class-relationships.md` |
| **品質** | 品質檢查清單 | 使用中 | `docs/04-deliver/E8--security-and-readiness-checklists.md` |
| **品質** | 部署與運維指南 | 草稿 | `docs/04-deliver/E9--deployment-and-operations-guide.md` |
| **品質** | Code Review 指南 | 草稿 | `docs/02-design/E6x--code-review-and-refactoring.md` |
| **支援** | 專案結構指南 | 活躍 | `docs/02-design/E6x--project-structure-guide.md` |
| **支援** | 前端架構規範 | 草稿 | `docs/02-design/E5x--frontend-architecture.md` |
| **支援** | 前端信息架構 | 草稿 | `docs/01-define/frontend-information-arch.md` |
| **支援** | 文檔與維護指南 | 草稿 | `docs/04-deliver/E9x--documentation-and-maintenance.md` |
| **支援** | 系統架構總覽 | 已完成 | `docs/00-discover/executive-architecture-overview.md` |
| **支援** | WBS 開發計畫 | 已定義 | `docs/01-define/E2x--wbs-project-schedule.md` |

**當前進度**: Phase 0（需求定義與架構設計）已完成。Phase 1（AI 客服 MVP）開發進行中。V2.0 業務服務已完成骨架搭建，16 個服務模組涵蓋 GAP 分析中全部 30 項缺口。14 份 V2.0 系統設計規格與 Agent Harness 重構文件持續演進中。
