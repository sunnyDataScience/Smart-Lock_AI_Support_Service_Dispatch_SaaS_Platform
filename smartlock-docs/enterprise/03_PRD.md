---
title: 產品需求文件（PRD）— Smart Lock AI 客服與派工 SaaS 平台
version: 1.0
status: active
owner: PM
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P1/05_platform_architecture_L1.md
  - smartlock-docs/00_platform/P1/06_platformization_strategy.md
  - smartlock-docs/00_platform/P1/07_workorder_platform_design.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P001_知識精煉獨立服務_draft審核後寫入.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P003_Casdoor_統一IdP_租戶_License.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P008_Model_Orchestration_Layer_供應商無關.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P010_Flow-as-Blocks_宣告式DSL_DSL-first.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P013_Agent_Configuration_Studio_品牌自服務.md
  - smartlock-docs/00_platform/P2/04_adr/ADR-P014_技師平台佣金邊界與工單CQRS投影.md
---

# 03 產品需求文件（PRD）

> 承接 [02_BRD](./02_BRD.md) 的業務規則，落為可實作、可驗收的功能需求。系統級規格下沉 [04_SRS](./04_SRS.md)；非功能指標見 [05_NFR](./05_NFR.md)；API 契約見 [16_API_Spec](./16_API_Spec.yaml)。

---

## 1. 文件元資訊

| 欄位 | 內容 |
|---|---|
| 結構 | Background / Problem / Goal / Non-goal / Scenario / Requirements / Metrics / Acceptance / Phasing |
| 需求編號 | FR-Gnn（G = 功能群 §7.1–§7.10，nn = 流水號）|
| 追溯 | FR ↔ BRD 業務規則 ↔ SRS ↔ Test Case（見 [21_Traceability_Matrix](./21_Traceability_Matrix.md)）|

---

## 2. Background（背景）

智慧鎖 AI 客服與派工 SaaS 平台，由 6 個系統組成：

| 系統 | 職責 | 部署歸屬 |
|---|---|---|
| **agent**（LockCore）| LINE Bot AI 客服：意圖分類、知識回覆、轉真人、對話記憶 | per-brand bundle |
| **api**（FastAPI）| 派工控制平面：問題卡 / 工單 / 報價 / 金流 / RBAC | per-brand bundle |
| **web**（Next.js）| 品牌營運後台（dispatch）+ Agent Configuration Studio | per-brand bundle |
| **knowledge-refinery** | 知識精煉：診斷 + 素材 → 事實 / 行為，HITL 審核（含獨立 web）| 集中共用 · License 附加 |
| **technician-platform** | 技師共享池（跨租戶）：身分 / 技能 / 排班 / 結算 + 獨立師傅 web | 集中共用 |
| **00_platform 整合層** | Casdoor（IdP + 租戶 + License）、SigNoz、Kafka 🔜、平台維運 console | 集中共用 |

商業模式為 **License 開通**（詳 [02_BRD](./02_BRD.md) §2.2）：品牌授權開通 per-brand bundle + 綁 LINE，附加模組按 License 加購。平台長期定位為「通用工單維運核心 + Vertical Pack 產業配置層」——同一核心可落地任何需要「工單 + 客服」的藍領產業。

## 3. Problem（問題陳述）

1. **報修非結構化**：LINE 對話中的品牌 / 型號 / 症狀 / 地址靠人工反覆追問，無法直接驅動派工。
2. **知識不可複製**：診斷 know-how 存在老師傅腦中，客服訓練期 3 個月，離職即歸零。
3. **金額與承諾失控**：口頭報價、現場隨意加價、AI 若可自由發話會做出賠償級承諾。
4. **三方帳對不平**：品牌、平台、技師各記各的帳，佣金與退款每月爭議。
5. **每個新品牌 / 新產業都像重寫一次系統**：流程、欄位、知識、UI 全部客製。
6. **合規要求高強度存證**：情緒識別、覆核紀錄、個資保留期，做不到即合約終止。

## 4. Goal（目標）

- **G1**：LINE 進線的報修，AI 於 5 秒（p95）內首次回應，自助解決率 ≥ 60%，急件 5 分鐘內到真人。
- **G2**：對話自動轉為結構化問題卡（completeness gate ≥ 0.85），1-click 進入工單流。
- **G3**：報價 → 客戶 LINE/LIFF 確認 → 派工 → 現場存證 → 結算，全鏈每一步有硬閘與 audit。
- **G4**：AI 職責邊界以確定性程式強制（白名單工具 + guardrail + 200 題 Eval 阻擋部署）。
- **G5**：佣金採計費（品牌）/ 結算（技師平台）分離，技師跨品牌單一對帳。
- **G6**：工單流程配置驅動（flow DSL + 積木），改流程不改碼；新產業 = 換一套 Vertical Pack。
- **G7**：品牌自主：License 開通、租戶自助開帳、Agent Studio 自服務調校。

## 5. Non-goal（非目標）

| 非目標 | 說明 |
|---|---|
| AI 自動開工單 / 派工 / 產生 final 報價 / 碰金流 | 永遠需人 1-click 確認；AI 只給範圍價 |
| AI 影像辨識 | 合約明文禁止；圖片僅附件 |
| flow 內嵌任意 code 節點（inline script）| 拒絕（ADR-P010）；逃生艙僅 plugin SDK + webhook 外呼 |
| 線上金流 / 消費者 App / 多語言 / 語音 / GPS 追蹤 / 庫存 | 見 [02_BRD](./02_BRD.md) §9.2 |
| 第 2 產業 Vertical Pack | Phase 4 roadmap，首發垂直為 locksmith |
| 全 no-code 覆蓋所有垂直長尾 | 長尾走逃生艙，不追求 100% 拖拉覆蓋 |

## 6. User Personas & Scenarios（角色與情境）

角色模型（四方 + 外緣）以 [02_BRD](./02_BRD.md) §3 / ADR-P006 為權威。

### 6.1 終端客戶報修情境（主線）

LINE 發訊 →「門鎖沒電打不開」→ AI 意圖分類 → 判定急件（被鎖門外）→ 5 分鐘內轉真人 + AI 草擬問題卡 → 小編補齊型號地址 → 急件 carve-out 直接開單並派工（跳過事前報價）→ 技師到府 → 完工三硬閘（照片 ≥ 3 + 簽名 + 序號）→ 4 小時內補送 retrospective 報價供客戶 LIFF 勾選同意（金額 / 車馬費 / 保固三條款）→ 客戶確認結案評分。
一般件主線：報價 Flex 推送 → 客戶 LIFF 確認 → 開單派工 → 技師到府（線上報價與現場不符時走現場報價修正輪 quote v+1 再確認）→ 施工完工 → 結案評分。
可自助情境：AI 依產品知識直接回覆操作步驟 → 主動詢問「問題釐清了嗎？」→ 客戶答已釐清 → 問題卡 resolved，全程不進派工。

### 6.2 報價確認三情境（對應 UC-019 / UC-020 / UC-021）

| 情境 | 流程要點 |
|---|---|
| **一般報價確認** | 小編送出報價（`POST /quotes/{id}:send-to-customer`）→ 客戶 LINE 收 Flex 摘要（AI 只告知存在，不複誦金額）→ LIFF 看明細 + 條款漸進揭露 → 勾 checkbox 確認（Idempotency-Key + confirm token TTL 48h）→ customer_confirmed 解鎖工單 |
| **急件事後補審** | 急件跳過報價直接開單施工 → onsite 結束 4h 內小編補送 retrospective 報價 → 客戶 LIFF 事後確認 / 紙本簽 → 解鎖結案 audit gate |
| **現場報價修正 re-quote** | 師傅到府複核發現線上報價與現場不符（估價誤差 / 加價 / 改項）→ 加價 ≥ 501 元暫停施工 → 系統自動建報價 v+1（快照串鏈）→ 分層核可（501–2000 小編 / >2000 主管；減價或同額修正直接送）→ 客戶 LIFF 確認 → 復工並更新料件；拒絕 → 按原報價完工 |

### 6.3 技師上架與工作情境

線上註冊（姓名 / 電話 / 專長）→ `pending_approval` → 後台核准 → `active` 可被派工（另有拒絕 / 暫停 / 復權 / 終止四種轉移，皆留稽核；terminated 不可逆）。日常：師傅 web 工作台看跨品牌派工（🔜 規劃中：Kafka 工單投影，Phase 3）→ 接單 → 到場 → 門檢 → 加價 re-quote → 完工回報 → 月結單一 statement。

### 6.4 品牌 onboarding 情境（FDE 4 配置面）

潛在品牌申請 → License 開通（Casdoor 訂閱）→ provisioning per-brand bundle + 綁 LINE（🔜 規劃中：自動化，Phase 3）。FDE 只做 4 件配置、核心程式不動：① 診斷系統（知識核心 + model 編排配方 + 調用效率）② 知識精煉（skill 行為 + RAG 語料）③ 工單 / 金流 flow DSL ④ 後台 UI 組裝（元件庫 + 自訂 panel）→ 打包 Vertical Pack@version → 品牌實例化 + 租戶級覆寫（價目 / SLA / 品牌參數）。

## 7. Requirements（功能需求）

> 每條需求為可追溯的功能能力陳述；🔜 標示 roadmap 項（見 §10 分期）。

### 7.1 AI 客服模組（agent / LockCore）

| ID | 需求 | 優先級 |
|---|---|---|
| FR-A01 | LINE webhook 接收（文字 / 圖片 / 位置 / Quick Reply），驗 X-Line-Signature；訊息 debounce 800ms ± 100ms | P0 |
| FR-A02 | 意圖分類 + 紅線決策樹（依 SOP 行為層 skill）；急件 4 類（被鎖門外 / 門內受困 / 安全風險 / 高風險怒客）繞過自助層強制轉真人 | P0 |
| FR-A03 | 三層解決機制：案例庫 → 手冊 RAG → 轉真人；知識回覆引用產品知識事實層；RAG 檢索經 MCP server 查 pgvector 唯一事實語料（🔜 語義層 Phase 2）| P0 |
| FR-A04 | `transfer_to_human` 為 AI 進後台唯一入口，附 escalation 原因 + 脈絡快照；真人接管中 AI 暫停回覆僅持久化訊息 | P0 |
| FR-A05 | per-user 對話記憶（租戶 + 使用者複合鍵），每輪結束抽取寫入 | P0 |
| FR-A06 | 工具白名單僅 6 項：`read_file / list_dir / find_files / grep / web_search / transfer_to_human`；白名單集中單點控管，新增工具屬架構變更 | P0 |
| FR-A07 | Guardrail：報價金額 / 折扣 / 免費保固攔截重生成；prompt injection 攔截 ≥ 95%；輸出限定產業話題；`rule_triggered_by` 由確定性引擎寫入 | P0 |
| FR-A08 | 多模態：圖片僅作附件與品質檢查（模糊 / 格式不符 → 引導重拍），禁 image-to-text；completeness 不足觸發 Flex 照片引導 | P0 |
| FR-A09 | 模型呼叫失敗回哨兵值 → 閘道以友善文字回覆，不外洩錯誤；模型調用經 Model Orchestration Layer（供應商 = 配置字串，多供應商 failover 🔜）| P0 |
| FR-A10 | AI 禁區 200 題 Eval pipeline：每次 deploy 自動跑，pass < 95% 阻擋部署 | P0 |

### 7.2 問題卡與派工

| ID | 需求 | 優先級 |
|---|---|---|
| FR-B01 | AI 自動草擬問題卡（`incomplete`），欄位：品牌 / 型號 / 症狀 / 急件類別 / completeness score / 媒體引用 | P0 |
| FR-B02 | completeness gate：≥ 0.85 方可 confirmed；同一 active issue 僅一張卡（唯一鍵約束）| P0 |
| FR-B03 | 小編補齊 + 確認 → 1-click 開立工單（公開單號）；`create_trigger` 記錄 AI 路徑（客戶觸發）或 CS 路徑（小編觸發）| P0 |
| FR-B04 | 工單成立硬綁定：Quote = customer_confirmed 或急件類別非空（BR-WO-01）| P0 |
| FR-B05 | 派工媒合：經技師平台 OHS API 查詢 / 媒合 `active` 技師；接單 SLA 一般 10 分 / 急件 5 分 + per-brand override；30 分無人接 → 擴大範圍 + 通知 | P0 |
| FR-B06 | 工單事件時間軸（event sourcing：seq / actor / from→to / payload）+ WebSocket 即時推播後台（Redis pub/sub fanout）| P0 |
| FR-B07 | LINE 外送一律經 outbox 佇列（10 秒輪詢 + 重試），與業務邏輯解耦 | P0 |

### 7.3 報價引擎

| ID | 需求 | 優先級 |
|---|---|---|
| FR-C01 | 報價生命週期：draft → internal_approved → customer_sent → customer_confirmed / rejected / expired（48h）；re-version v+1 以 `supersedes_quote_id` 串鏈 | P0 |
| FR-C02 | 定價引擎為獨立 bounded context（`api/pricing/`）：quote 經 in-process call 取價；AI 禁止直接呼叫；引擎故障 → 後台 banner + 小編手填降級模式 | P0 |
| FR-C03 | 每筆報價綁不可變 content-addressable 快照（`pricing_rule_snapshot` keyed by sha256，append-only）；已送出報價永不重算 | P0 |
| FR-C04 | 客戶 LIFF 確認：明細 + 條款漸進揭露 + checkbox 同意；`POST /quotes/{id}/customer-confirm`（Idempotency-Key + confirm token TTL 48h）；consent 方式記錄（liff_full / flex_simple_fallback）| P0 |
| FR-C05 | AI 報價邊界 server-side 強制：AI 訊息用 server 模板（無自由文金額）；保固 / 建案案件 AI 觸發送出 → 403 | P0 |
| FR-C06 | 急件 retrospective 報價：4h 內補送 + 事後確認；逾時 audit alert 升級；定價規則變更走 ChangeRequest 四級授權矩陣（[02_BRD](./02_BRD.md) §6.3）| P0 |

### 7.4 現場維修

| ID | 需求 | 優先級 |
|---|---|---|
| FR-D01 | 到府流程：到場事件 → 到府同意書 → 門檢（門檢須先有到場事件）| P0 |
| FR-D02 | 加價三段式：≤500 師傅自確 + 三件套；501–2000 暫停施工 + 報價 v+1 客戶確認；>2000 加主管覆核 + 三方協商 | P0 |
| FR-D03 | LIFF 失敗 fallback：QR code → 紙本簽 + 拍照 + audit；客戶拒絕 → customer_disagreed_partial 按原報價完工 | P0 |
| FR-D04 | 完工三硬閘：照片 ≥ 3 + 客戶簽名 + 安裝序號（主鎖與 >1000 元零件強制）；料件 owner 三選一標記 | P0 |
| FR-D05 | Evidence 生命週期管理：sha256 主鍵、retention 分類、legal hold、兩階段清除（T0 金鑰銷毀 → T+30 硬刪）| P0 |

### 7.5 結算與佣金

| ID | 需求 | 優先級 |
|---|---|---|
| FR-E01 | 收款登錄：現場 / 繳費連結 / 匯款；對帳狀態機（deposit_required → paid → pending → 入帳 / failed）| P1 |
| FR-E02 | 品牌側計費（Billing）：per-job 佣金明細（工單金額 / 料件 / 完工）→ 發 `commission.accrued` 事件（outbox；🔜 Kafka Phase 3）| P1 |
| FR-E03 | 技師平台結算（Settlement）：訂閱佣金事件 → 跨品牌彙總 / statement / payout；期末 reconcile 對帳閘門 🔜 Phase 3 | P1 |
| FR-E04 | 帳本 append-only + reversal entry 更正；退款 5×3 責任分層；車馬費 80/20 + 距離級距 + per-contract override | P1 |
| FR-E05 | 月結匯出（品牌會計格式），退件率量測 ≤ 5% | P1 |

### 7.6 通用工單平台能力（Vertical Pack / flow DSL / 積木）

| ID | 需求 | 優先級 |
|---|---|---|
| FR-F01 | 工單領域模型 = 通用核心欄（客戶 / 地點 / 狀態 / 指派 / 金額 / 時間軸）+ `attributes JSONB` 產業欄位 + `field_metadata`（type / required / options / validation / ui_hints）驅動語義；加欄位不改 schema 不寫 code | P1 |
| FR-F02 | flow DSL（宣告式狀態機：states / transitions / guards / actions / SLA）為工單生命週期的**資料**；引擎解釋執行：guard 檢查（RBAC claim + precondition）→ 執行積木 → 持久化 + 事件溯源 + SLA timer；冪等（event seq + idempotency key）+ outbox | P1 |
| FR-F03 | 積木雙層顆粒度：對外粗顆粒 domain block（dispatch / quote_approval / onsite_consent / collect_payment / settle…）有契約（inputs / preconditions / guards / effects）；內部細顆粒 primitives 組合 | P1 |
| FR-F04 | 逃生艙：plugin SDK（型別安全 + 審查 + 版本化）+ webhook 外呼；**拒 inline code 節點** | P1 |
| FR-F05 | Vertical Pack manifest：`field_metadata + flow + catalog + knowledge + ui_composition + blocks`，語意版本化；可 `extends` 藍領基底 pack；品牌 = pack@version + 租戶覆寫 | P1 |
| FR-F06 | 後台兩層渲染：欄位層 `DynamicForm` / `DynamicTable` 配置驅動；畫面層 `ui_composition` 元件組裝（WorkOrderBoard / DispatchConsole / QuotePanel / FinancePanel / EvidenceViewer / CustomerTimeline）+ 自訂 panel | P1 |
| FR-F07 🔜 | 拖拉 FlowEditor（薄編輯器，產出 / 編修 DSL）— Phase 4，DSL-first 鐵律：引擎先於 UI | P2 |
| FR-F08 🔜 | AI Onboarding Compiler：客戶 SOP / 訪談 → Block Ontology 對映 → draft flow DSL + 缺口標記 → HITL 人審匯入（金流 / 派工 / 同意書流程必過人審）— Phase 4 | P2 |

### 7.7 知識精煉（knowledge-refinery）

| ID | 需求 | 優先級 |
|---|---|---|
| FR-G01 | 獨立容器服務 + 自有 web 介面（License 附加模組）；輸入：診斷對話 + 產品素材，Medallion raw → bronze → silver 治理；**bronze-only sourcing**（PDF 類不可信來源只引 URL 不抄內容）| P1 |
| FR-G02 | LLM 提煉分流：事實（manual_chunks / case_entries）與行為 / 精選（skill 規範），append-only | P1 |
| FR-G03 | HITL 審核 UI：diff 檢視 → 核可 / 拒絕 / 退回重煉；核可後事實 chunk+embed 灌 pgvector、行為更新 skill（git-tracked）| P1 |
| FR-G04 | references ↔ pgvector 同源 CI 檢查；審核 UI 走 Casdoor OIDC 🔜 Phase 2 | P1 |
| FR-G05 | Agent Configuration Studio（ADR-P013）：品牌 web 自服務調校——skill 匯入 / 編輯（客製層）、RAG 語料檢索權限開關（ACL 於 MCP-RAG 查詢時強制，跨租戶隔離平台鎖死）、system prompt 版本化 + 回滾 + eval gate；**受保護層（escalation / domain-safety / 合規語氣 / 資料邊界）品牌不可 override**；高風險改動選配 HITL；集中 Agent Config Registry（skill 庫 + RAG 源目錄 + prompt 範本）| P1 |

### 7.8 身分 / 租戶 / 授權

| ID | 需求 | 優先級 |
|---|---|---|
| FR-H01 | Casdoor 統一 IdP（OAuth2/OIDC）：各服務驗 OIDC token；web 授權碼流，token 安全儲存（httpOnly cookie）🔜 Phase 2 | P0 |
| FR-H02 | 四方 RBAC enforce：Casdoor 發角色 claim，api resource-level `role_required` 實際阻擋，deny-by-default；web 路由 gate 讀 OIDC claim | P0 |
| FR-H03 | 租戶 = Casdoor org；租戶 Admin 自助開通帳號給自己人 🔜 Phase 2 | P1 |
| FR-H04 | License 開通：Casdoor subscription / pricing 管理品牌授權與到期，作為 per-brand provisioning 開通閘門；模組級開通（基礎 bundle / refinery / compiler）| P1 |
| FR-H05 | SoD：敏感操作 X-Initiator / X-Approver / X-Executor 任二相同 → 403；服務間 internal token fail-closed（常數時間比對）| P0 |
| FR-H06 | tenant_id 貫穿 API / DB / AI 記憶；跨租戶零洩漏；機密一律 Secret Manager 注入 | P0 |

### 7.9 平台維運（Super Admin）

| ID | 需求 | 優先級 |
|---|---|---|
| FR-I01 | 平台維運 console（中央部署，Super Admin web）：跨租戶治理、品牌申請審核、License 管理 | P1 |
| FR-I02 | 可觀測性分層：SigNoz 系統層（OTel，全服務，prod 常開）+ OPIK agent LLM Ops（dev 必開 / prod 可關）| P0 |
| FR-I03 | KPI dashboard（K1–K11 + AI 模組層指標）+ 合規即時監控 + counter-metric 告警（詳 [25_Monitoring_Spec](./25_Monitoring_Spec.md)）| P1 |
| FR-I04 🔜 | License → provisioning 自動化：開通 → 部署 bundle → 建庫 → 綁 LINE（Phase 3，依 CD pipeline）| P2 |

### 7.10 技師平台（technician-platform）

| ID | 需求 | 優先級 |
|---|---|---|
| FR-J01 | 技師身分單一真相：跨租戶身分 / 技能 / 品牌授權 / 認證（KYC）/ 排班 / 評分，自有庫 `lock_tech`；派工平台經 OHS API 串接，**不直連技師庫** | P1 |
| FR-J02 | 獨立師傅 web：註冊（email + 角色複合唯一，同一人可兼技師與廠商身分）→ pending_approval → 後台核准 → active；上線 / 排班 / 工作台 | P1 |
| FR-J03 | 技師生命週期：核准 / 拒絕 / 暫停 / 復權 / 終止（terminated 不可逆），全程稽核事件 | P1 |
| FR-J04 🔜 | 跨品牌工單投影（CQRS read-model）：訂閱 `workorder.{dispatched,updated,completed}` 事件維護技師視角投影；欄位最小化（摘要 / 地址 / 狀態 / 時窗 / 金額）— Phase 3 | P1 |
| FR-J05 🔜 | 結算主體：訂閱 `commission.accrued` → 跨品牌 statement / payout / 對帳 — Phase 3 | P1 |

## 8. Metrics（成功指標）

商業 KPI 全表為 [02_BRD](./02_BRD.md) §7 權威。產品驗證映射：

| 需求群 | 驗證指標 |
|---|---|
| §7.1 AI 客服 | K1 準確率 ≥ 80%（內部 85%）· K2 自助 ≥ 60% · K6 首答 5s p95 · K8 禁區 Eval ≥ 95% · 意圖分類 ≥ 85% · handoff ≤ 30%（不 < 5%）· debounce 800ms | 
| §7.2 問題卡派工 | 問題卡自動建立成功率 ≥ 70%（re-edit ≤ 20%）· K5 接單 SLA 達成 ≥ 95% |
| §7.3 報價 | 快照 hash mismatch 0 / 月 · guardrail 攔截率 100% |
| §7.5 結算 | K11 月結退件 ≤ 5% · 期末 reconcile 對平率 [待確認] |
| §7.7 知識 | RAG 引用率 ≥ 90% · stale source ≤ 10% · long-tail 命中 ≥ 60%（Phase 2）|
| §7.8 身分 | 未授權寫入阻擋率 100%（deny-by-default）· 跨租戶洩漏 0 |
| 全平台 | K7 uptime ≥ 95%（合約）/ 99.5%（內部）· K9 同時在線 50 → 100 |

## 9. Acceptance Criteria（驗收標準）

| 群組 | 可驗收條件（節錄；BDD 場景見 [19_Test_Plan](./19_Test_Plan.md) / [20_Test_Cases](./20_Test_Cases.md)）|
|---|---|
| AI 客服 | 急件 4 類 100% 於 5 分內轉真人；200 題禁區 Eval ≥ 95% 否則 deploy 被 block（CI 強制）；guardrail 紅軍測試攔截率 100%；負面情緒識別 ≥ 90%（UAT 標準集）；image-to-text 呼叫數 = 0（pre-commit + runtime 雙閘）|
| 問題卡 | completeness < 0.85 無法 confirmed；同 active issue 第二張卡被唯一鍵拒絕；地址空值時結案 API 回 422 |
| 報價 | AI 送出保固 / 建案報價 → 403 AI_FORBIDDEN；已送出報價在規則變更後金額不變（快照驗證）；LIFF 確認冪等（重放同 Idempotency-Key 不重複轉態）|
| 工單 | Quote 未 customer_confirmed 且非急件 → 工單無法成立；急件逾 4h 未補審 → audit alert 產生；完工缺任一硬閘（照片 / 簽名 / 序號）→ 拒絕 |
| 現場 | 加價 501 元起工單施工被暫停且師傅不可改料件明細；客戶拒絕 v+1 後按原報價金額結算 |
| 結算 | 帳本 UPDATE / DELETE 被 DB 約束拒絕；佣金事件與品牌計費彙總 reconcile 對平 |
| 平台能力 | 修改 field_metadata 新增欄位後 DynamicForm 免部署渲染；手寫 flow DSL 匯入 → 引擎可執行且違反積木 precondition 的轉移被拒 |
| RBAC / SoD | 無角色 claim 的寫入請求 → 403（deny-by-default 全端點）；Initiator = Approver → 403 |
| 合規 | GDPR 遺忘 7 天內完成或發 notice；legal hold 下清除請求被拒；家族覆核 event log 完整率 ≥ 95% |

## 10. Scope & Phasing（範圍與分期）

| Phase | 交付功能（FR 對映）| 前置依賴 |
|---|---|---|
| **Phase 1**（正確性與即時）| RBAC deny-by-default 全端點（FR-H02，先高風險金流 / 派工端點）· Redis pub/sub + 分散式鎖 + 連線池（FR-B06）· SigNoz + OPIK 接通（FR-I02）· AI 禁區 Eval 常態化（FR-A10）· 工單全鏈主流程（§7.1–§7.4）| — |
| **Phase 2**（身分 / 知識 / 技師平台）| Casdoor OIDC 全面導入 + 租戶自助開帳（FR-H01/H03）· RAG-via-MCP 語義層（embed + cosine query + MCP server）與語料灌注（FR-A03/G03）· technician-platform 獨立系統 + OHS API（FR-J01–J03）· 讀寫分離（read replica）| Phase 1 |
| **Phase 3**（事件骨幹與規模化）| Kafka 事件骨幹：工單 / 技師 / 佣金事件 + schema registry + 契約測試（FR-E02/E03/J04/J05）· per-brand provisioning 自動化 + CD（FR-I04）· 對帳閘門 | Phase 2 |
| **Phase 4**（平台化飛輪）| 通用工單核心表重構（core + JSONB + field_metadata，FR-F01）→ locksmith Vertical Pack v0（FR-F05）→ 第 2 產業驗證 → FlowEditor + AI Onboarding Compiler（FR-F07/F08）| flow DSL 引擎穩定（DSL-first）|

工單平台子路線（`../00_platform/P1/07_workorder_platform_design.md` §8）：① DSL schema + 積木契約 + 引擎（手寫 DSL 可執行 / 驗證）→ ② 核心表重構 → ③ locksmith pack → ④ 第 2 產業 → ⑤ 編輯器 + AI 編譯。

## 11. Dependencies & Risks（依賴與風險）

| 依賴 / 風險 | 影響 | 緩解 |
|---|---|---|
| LINE Messaging API（webhook / Reply / Push）| 客戶通道單點 | webhook HA（retry / DLQ / 24h dedup）|
| LLM 供應商（Vertex AI / Gemini 等）| 回答品質與成本 | Model Orchestration Layer：供應商 = 配置、failover、快取 / 批次 / 重試集中治理（ADR-P008）|
| Casdoor | 全平台身分單點 | HA + 備份；License 語義超出內建能力時補 license 服務層 |
| Kafka（Phase 3）| 投影 / 結算最終一致性 | 事件 schema registry + consumer-driven 契約測試 + 期末 reconcile |
| DSL 設計品質 | 「皇冠寶石」，設計壞整條鏈歪 | DSL-first 鐵律：先引擎後 UI；積木契約靜態可驗證 |
| 積木飛輪冷啟動 | 頭 2-3 產業 AI 命中率低 | 積木手工建；不過早對外承諾「AI 一鍵匯入」|
| 品牌自服務調校風險 | prompt / skill 誤改影響真實對話 | 受保護層不可 override + eval gate + 版本回滾 + audit + 選配 HITL（ADR-P013）|
| 合約紅線（R-F4）| 未達標可終止合約 | 見 [02_BRD](./02_BRD.md) §8；紅線項全數列入 UAT |

## 12. 追溯

| FR 群 | BRD 規則 | 上位 ADR | 下游 |
|---|---|---|---|
| §7.1 | BRD §6.1 | ADR-P008 · agent ADR-004 | 04_SRS · 16_API_Spec · 19_Test_Plan |
| §7.2–§7.4 | BRD §6.2/6.4/6.5 | ADR-P010 · ADR-P004 | 08_User_Flow · 18_DB_Design |
| §7.3 | BRD §6.3 | 定價快照決策群 | 16_API_Spec |
| §7.5 | BRD §6.6 | **ADR-P014** | 17_AsyncAPI · 15_SDS |
| §7.6 | BRD §2.3 | ADR-P009 / P010 / P011 | 15_SDS §flow |
| §7.7 | BRD §5.5 | ADR-P001 · ADR-P013 | 12_SAD |
| §7.8 | BRD §3 / §6.7 | ADR-P003 · **ADR-P006** | 13_Security_Architecture |
| §7.10 | BRD §6.6 | ADR-P004 · ADR-P014 | ../technician-platform/ 系統文件 |

---

*03_PRD v1.0 — 2026-07-07*
