# Smart Lock 平台文件庫

> **版本:** v2.0 | **建立:** 2026-07-07 | **涵蓋系統:** 6 個（4 as-is + 2 target 新系統）+ 平台整合視圖 | **來源:** 多 agent 排查現況 → 業主逐坑裁決演進為理想態 target
>
> **兩層並存**：平台層（`00_platform/`）已就地演進為 **理想態 target v2**（L1 v2 + 策略 + 工單 SDS + ADR-P001~P013）；各系統 P1–P4 仍以 **as-is 現況**為主體，並於 SAD 頂部加「🎯 target 態演進」段。as-is baseline 完整保存於 git `238f6fce`。
>
> **涵蓋範圍:** Smart Lock **AI 客服 + 派工 SaaS 平台**全系列子系統。
> 本文件庫的文件架構鏡像自 `acme-docs/`（VibeCoding_Workflow_Templates v3.x 分階模板：P1 架構 / P2 介面·部署 / P3 需求·安全 / P4 結構·BDD），但**內容 100% 為本專案現況**，非套用他案。
>
> ⚠️ **現況優先原則**：本庫描述「code 與 compose 實際長什麼樣」，凡與根目錄舊 `README.md` / `data/` 文件衝突者，**以本庫為準**（舊文件多描述 2026-06-04 前已被 LockCore 重寫 superseded 的架構）。凡未能由 code 證實者一律標 `[待確認]`。

---

## 快速導覽

| 我想… | 去哪裡 |
| :--- | :--- |
| 了解整個平台架構（有哪些系統） | [`00_platform/P1/05_platform_architecture_L1.md`](00_platform/P1/05_platform_architecture_L1.md) |
| 看跨系統資料流 DAG | [`00_platform/P2/09_integration_data_flow.md`](00_platform/P2/09_integration_data_flow.md) |
| 查某系統的架構圖 | `{系統}/P1/05_architecture_and_design.md` |
| 查某系統的軟體需求規格 (SRS) | `{系統}/P3/02a_software_requirements_specification.md` |
| 查某系統的軟體設計規格 (SDS) | `{系統}/P1/05a_software_design_specification.md` |
| 查 API 端點 / 介面契約 | `{系統}/P2/06_api_design_specification.md` |
| 了解技術選型原因 | `{系統}/P2/04_adr/` |
| 做安全評估 | `{系統}/P3/13_security_checklist.md` |
| 看業務需求 / 用戶故事 | `{系統}/P3/02_project_brief_prd.md` |
| 規劃重構 | `{系統}/P4/08_project_structure_guide.md` |
| 補測試場景 | `{系統}/P4/03_bdd_guide.md` |

### 🎯 理想態（target v2）導覽

| 我想… | 去哪裡 |
| :--- | :--- |
| 看 target 平台架構 + 6 系統 + DDD | [`00_platform/P1/05_platform_architecture_L1.md`](00_platform/P1/05_platform_architecture_L1.md)（v2）|
| 平台化策略 + 護城河（TRIZ／積木飛輪／AI 編譯器）| [`00_platform/P1/06_platformization_strategy.md`](00_platform/P1/06_platformization_strategy.md) |
| 通用工單維運平台詳細設計（SDS）| [`00_platform/P1/07_workorder_platform_design.md`](00_platform/P1/07_workorder_platform_design.md) |
| target 架構決策（ADR-P001~P013）| [`00_platform/P2/04_adr/`](00_platform/P2/04_adr/) |

---

## 系統清單

平台為 **monorepo**。**as-is 現況 4 系統** + **target 理想態新增 2 系統**（knowledge-refinery／technician-platform）。子系統「多面性」是重要特徵：web/api 各一份 codebase 靠旗標塑多部署面。target 態結構（per-brand bundle vs 集中共用 vs License 附加）見 `00_platform/P1/05` L1 v2。

| 系統 | 角色 | 定位 | 文件夾 |
| :--- | :--- | :--- | :--- |
| **agent** | LINE Bot AI 客服（LockCore）| as-is + 🎯 target 段（RAG-MCP／OPIK／Model Orchestration／Agent Studio）| [`agent/`](agent/) |
| **api** | 派工營運控制平面（工單/帳務/結算）| as-is + 🎯 target 段（RBAC enforce／Casdoor／Redis-Kafka／通用工單引擎）| [`api/`](api/) |
| **web** | 多站營運前端 | as-is + 🎯 target 段（Casdoor OIDC／師傅端移出／元件庫組裝／Agent Studio）| [`web/`](web/) |
| **knowledge-refinery** 🎯 | 知識精煉服務 + 審核 UI（License 附加）| target 新系統（由 data-pipeline 升格，ADR-P001）| [`knowledge-refinery/`](knowledge-refinery/) |
| **technician-platform** 🎯 | 技師共享池獨立系統（跨租戶 + 師傅 web）| target 新系統（由 tech-db/tech-api 升格，ADR-P004）| [`technician-platform/`](technician-platform/) |
| ~~data-pipeline~~ | 離線 Medallion（as-is）| ⚠️ target 已升格為 knowledge-refinery | [`data-pipeline/`](data-pipeline/) |

> **資料層（DB）** 不獨立成系統，依 acme-docs 慣例歸屬其擁有者：`api` 擁有全業務 schema（~100 表，pgvector），`agent` 擁有 `agent.*` 記憶 schema。DB 的三向分裂（品牌庫/技師庫/平台庫）屬跨系統議題，於 `00_platform/` 詳述。

### 使用者角色 → 進入點

| 角色 | 進入系統 | 協議 |
| :--- | :--- | :--- |
| 智慧鎖終端客戶（消費者）| **agent**（LINE 官方帳號）| LINE webhook |
| 品牌營運人員 | **web** dispatch portal :3000 → api dispatch :8001 | HTTPS / WebSocket |
| 簽約師傅 | **web** tech portal :3001 → api tech :8002（WS 走 :8001）| HTTPS / WebSocket |
| 平台管理員 | **web** platform portal :3003 → api platform :8003 | HTTPS |
| 潛在加盟品牌 | **web** landing :3002 → api platform :8003（品牌申請）| HTTPS |

---

## 文件結構（完整規劃）

```
smartlock-docs/
│
├── README.md                                    ← 本文件（總索引）
│
├── 00_platform/                                 ← 跨系統整合視圖
│   ├── P1/
│   │   └── 05_platform_architecture_L1.md      ← C4 L1 + DDD Context Map + 整合矩陣 + 缺口清單 ✅
│   └── P2/
│       └── 09_integration_data_flow.md         ← 跨系統資料流 DAG + 關鍵路徑 + 風險 ✅
│
├── agent/            (LockCore LINE Bot AI 客服)
│   ├── P1/  05_architecture_and_design.md · 05a_software_design_specification.md · 16_wbs_development_plan.md
│   ├── P2/  06_api_design_specification.md · 14_deployment_and_operations_guide.md · 04_adr/
│   ├── P3/  02_project_brief_prd.md · 02a_software_requirements_specification.md · 09_file_dependencies.md · 13_security_checklist.md
│   └── P4/  08_project_structure_guide.md · 03_bdd_guide.md
│
├── api/              (FastAPI 派工營運控制平面)
│   └── P1–P4 同上結構
│
├── web/              (Next.js 多站前端)
│   └── P1–P4 同上結構
│
└── data-pipeline/    (離線 Medallion 數據中台)
    └── P1–P4 同上結構
```

> **每系統 12 份文件模板**（同 acme-docs）：
> - **P1**：`05` 架構設計 (SAD, C4/DDD/DFD/部署/NFR) · `05a` 詳細設計 (SDS, IEEE 1016) · `16` WBS 開發計畫
> - **P2**：`06` API/介面契約 · `14` 部署運維指南 · `04_adr/` 架構決策紀錄
> - **P3**：`02` PRD · `02a` SRS (IEEE 29148) · `09` 模組依賴 · `13` 安全檢查清單
> - **P4**：`08` 結構指南 · `03` BDD 指南

### 本次生成狀態

| 批次 | 內容 | 狀態 |
| :--- | :--- | :--- |
| 平台層 | README + L1 架構 + 整合資料流 | ✅ 已產出 |
| 各系統 P1/05 SAD | 4 系統架構設計文件 | ✅ 已產出 |
| 各系統其餘 P1–P4 | SRS/SDS/API/ADR/安全/結構/BDD/PRD/WBS/依賴/部署 | 🔄 依此結構逐系統回補（分階交付）|

---

## 平台級關鍵架構缺口（現況，待處理）

> 完整清單與風險分級見 `00_platform/P1/05_platform_architecture_L1.md §5` 與 `00_platform/P2/09_integration_data_flow.md §6`。

| 缺口 | 風險 | 建議行動 | 相關文件 |
| :--- | :--- | :--- | :--- |
| **雲/本機拓撲不對稱** — 本機 5-bundle 多 surface；雲端只 3 Cloud Run（api 用 `API_SURFACE=all` 單體，無 tech/platform/landing 雲端部署，技師庫雲端未接）| 🔴 高 | 對齊雲端拓撲或明確文件化「雲端單體、本機多面」為刻意設計 | `00_platform` · `api/P2/14` |
| **RBAC 授權矩陣仍 shadow-mode** — 80+ 敏感寫入端點僅檢租戶不檢角色，矩陣 log-only 永不擋 | 🔴 高 | 逐端點補 `role_required`；矩陣轉 enforce | `api/P3/13` |
| **即時通道 in-memory 單機** — WS hub + 11 cron worker 皆進程內，Cloud Run 多實例跨實例事件遺失、cron 重複跑 | 🔴 高 | 導入 Redis pub-sub + 分散式排程 | `api/P1/05` · `00_platform/P2/09` |
| **data-pipeline 產出鏈斷開** — `silver_to_skill` 寫入不存在的死目錄，文件描述 superseded 舊架構 | 🔴 高 | 修復產出目標對齊 lockcore references，或正式標記管線退役 | `data-pipeline/P1/05` |
| **兩套知識系統無收斂** — pgvector RAG（後台）vs filesystem references（agent）來源不同、雙維護、無同步 | 🟡 中 | 定義單一知識真相源 + 同步機制 | `data-pipeline/P1/05` · `agent/P1/05` |
| ~~**兩個 LINE webhook 分流不明**~~ **已決議（CR-0121 方案 A + ADR-005）** — agent `/callback` 為 LINE 唯一入站門 + postback 前綴 fan-out；api `/line/webhook` 退役 | 🟢 已收斂（待 code 實作）| 依 CR-0121 §9 實作 fan-out + `/internal/*` 端點 | `00_platform/P2/09` · `CR-0121` · `ADR-005` |
| **無統一 Auth / API Gateway** — 認證分散各 api，JWT 密鑰隔離靠部署紀律（同名 env 不同值）| 🟡 中 | 評估集中式 identity / gateway | `api/P3/13` |
| **v1→v2 API cutover 未完成** — v1/v2 雙掛，DeprecationMiddleware 仍在用，多份 CIA 待業主裁決 | 🟡 中 | 收尾 P4 cutover gate | `api/P1/16` |
| **Migration registry 雙向漂移** — 純 SQL forward-only，狀態標記自承「意圖非事實」，046 前歷史不可考 | 🟡 中 | 建 CI schema 比對 | `data-pipeline/P1/05` |

---

> 本文件庫由 Claude Code 多 agent 排查後綜合生成，文件架構鏡像 `acme-docs/`（VibeCoding_Workflow_Templates）。
> 生成日期：2026-07-07 | 佐證來源：`web/api/agent/data/SQL/scripts/*.compose` 實際 code（各事實表附 file:line）
