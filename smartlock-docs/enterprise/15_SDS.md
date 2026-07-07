---
title: 軟體詳細設計書（SDS）— Smart Lock AI 客服與派工 SaaS 平台
version: 1.0
status: active
owner: 平台架構師
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P1/07_workorder_platform_design.md
  - smartlock-docs/00_platform/P2/09_integration_data_flow.md
  - smartlock-docs/00_platform/P2/04_adr/（ADR-P001, P004, P007, P008, P009, P010, P011, P014）
  - smartlock-docs/agent/P1/05_architecture_and_design.md
  - smartlock-docs/api/P1/05_architecture_and_design.md
  - smartlock-docs/technician-platform/P1/05_architecture_and_design.md
  - smartlock-docs/web/P1/05_architecture_and_design.md
  - smartlock-docs/knowledge-refinery/P1/05_architecture_and_design.md
---

# 15. 軟體詳細設計書（SDS）

## 1. 文件元資訊與範圍

| 欄位 | 內容 |
|---|---|
| 層級 | 系統詳細設計（C3/L3 元件、狀態機、關鍵序列、健壯性機制）|
| 上位文件 | [12_SAD](./12_SAD.md)（容器級架構）· [13_Security_Architecture](./13_Security_Architecture.md)（安全政策）· [14_ADR/](./14_ADR/)（決策紀錄）|
| 下位對接 | [16_API_Spec](./16_API_Spec.yaml)（REST schema）· [17_AsyncAPI](./17_AsyncAPI.yaml)（事件契約）· [18_DB_Design](./18_DB_Design.md)（DDL/索引）· [19_Test_Plan](./19_Test_Plan.md) |
| 範圍 | 通用工單維運平台核心 + 六個子系統（agent / api / technician-platform / web / knowledge-refinery / 平台整合層）的內部元件設計 |
| 不含 | NFR 量化數字（歸 [05_NFR](./05_NFR.md)）、安全政策正文（歸 13）、API/事件 schema 正文（歸 16/17）、DDL（歸 18）、部署與維運（歸 [23](./23_Deployment_Guide.md)/[24](./24_Runbook.md)/[25](./25_Monitoring_Spec.md)）|

分階段交付註記：本書描述完整設計；標 **🔜 規劃中** 者為已定案、分期落地的元件（如 Phase 2 導入 Redis/Kafka 事件骨幹、Phase 5 導入 AI Onboarding Compiler），其餘為 Phase 1 交付範圍。

---

## 2. 設計總則

### 2.1 分層原則：可重用平台核心 vs 領域配置層（Vertical Pack）

```mermaid
flowchart TB
    subgraph CORE["可重用平台核心（FDE 永不動）"]
        ENG["工單引擎<br/>(flow DSL 執行器)"]
        LIB["共用 UI 元件庫"]
        FIN["金流/對帳/結算軌"]
        IDN["身分/RBAC/租戶<br/>Casdoor"]
        BUS["事件骨幹<br/>Kafka/Redis"]
    end
    subgraph CFG["領域配置層（FDE 每產業 4 配置面）"]
        FM["① 診斷系統<br/>知識+model 編排"]
        KN["② 知識精煉"]
        FL["③ flow DSL + 積木"]
        UI["④ UI 組裝"]
    end
    PACK["Vertical Pack 產業包（版本化）"]
    CFG --> PACK
    PACK -->|載入/實例化| CORE
    TEN["品牌（租戶）"] -->|裝一個 pack + 租戶設定| PACK
```

**核心原語**：引擎只認識「工單 / 狀態機 / 派工 / 報價 / 金流 / 事件」等產業無關概念；產業知識全在 Vertical Pack。新產業 = 裝一個 pack + 輕組裝，核心零改碼（ADR-P009）。

### 2.2 設計約束（引 14_ADR）

| 約束 | 內容 | 依據 |
|---|---|---|
| 核心 vs 配置分層 | 通用核心欄 + JSONB + field_metadata；Vertical Pack 為交付單位 | ADR-P009 |
| Flow-as-Blocks | 工單/金流流程為宣告式 DSL 資料，引擎解釋執行；DSL-first（先穩引擎，後疊 UI/AI）| ADR-P010 |
| 技師共享池獨立 | technician-platform 為獨立系統，`assignee_ref` 跨系統參照不 FK；整合走 OHS API + Kafka | ADR-P004 |
| 模型編排層 | 供應商 = 配置（LiteLLM model 字串路由）、多供應商 fallback、調用效率集中最佳化 | ADR-P008 |
| 佣金/工單投影邊界 | Billing 留品牌、Settlement 歸技師平台；工單可見性走 CQRS 投影 | ADR-P014 |
| 事件與即時 | Kafka 事件骨幹 + Redis pub/sub + 讀寫分離 | ADR-P007 |

### 2.3 跨系統元件命名與依賴方向

- **DIP**：agent→api（`/internal/*` 契約）、api→technician-platform（OHS API 契約），依賴由不穩定指向穩定。
- **ADP**：主依賴單向 `web → api → DB`、`agent → api`、`api → technician-platform`；技師平台與派工靠事件 + API，無服務循環。
- **SDP**：Casdoor / 品牌庫 / technician-platform 為最穩定核心，嚴控版本；web / knowledge-refinery 最不穩定、不被依賴。
- 分層命名慣例（全系統一致）：`routers/`（HTTP 入口 + 授權）→ `services/`（業務 + SQL）→ `core/`（橫切）；services 不 import routers。

---

## 3. 通用工單維運平台詳細設計

### 3.1 領域模型（通用核心欄 + attributes JSONB + field_metadata）

```mermaid
erDiagram
    WORK_ORDERS ||--o{ WORK_ORDER_EVENTS : timeline
    WORK_ORDERS ||--o{ QUOTES : has
    QUOTES ||--o{ QUOTE_LINE_ITEMS : contains
    WORK_ORDERS ||--o{ PAYMENTS : has
    WORK_ORDERS ||--o{ EVIDENCE : has
    WORK_ORDERS ||--o{ CONSENTS : has
    WORK_ORDERS }o--|| CUSTOMERS : for
    WORK_ORDERS }o..|| TECHNICIAN_PLATFORM : assignee_ref
    FIELD_METADATA ||..o{ WORK_ORDERS : "驅動 attributes 語義"
```

核心表（產業無關；`attributes JSONB` 承載產業欄位；DDL 全文見 [18_DB_Design](./18_DB_Design.md)）：

```sql
work_orders (
  id, tenant_id, industry_pack, pack_version,
  customer_id, location JSONB,          -- 地址/geo
  status TEXT,                          -- 值域由 flow DSL 定義（非 enum 寫死）
  priority, sla_due_at,
  assignee_ref TEXT,                    -- → technician-platform（跨系統 ref，不 FK，ADR-P004）
  quote_id, settlement_id, amount,
  attributes JSONB,                     -- 產業欄位：鎖{brand,model,serial,warranty} / HVAC{unit,refrigerant}
  created_at, updated_at
)
work_order_events (id, wo_id, seq, type, actor_ref, from_status, to_status, payload JSONB, at)  -- 事件溯源時間軸
quotes(id, wo_id, status, total, attributes JSONB)   quote_line_items(id, quote_id, catalog_ref, qty, unit_price, attributes JSONB)
payments(id, wo_id, method, amount, status, …)       settlements(id, …)
evidence(id, wo_id, kind, uri, meta JSONB)           consents(id, wo_id, kind, signed_by, uri, at)
field_metadata(pack, pack_version, entity, key, label, type, required, options JSONB, validation JSONB, ui_hints JSONB)
```

設計要點：

- **核心欄位 = 各產業不變的營運骨架**（客戶/地點/狀態/指派/金額/時間軸）→ 可查詢、可索引、可報表。
- **`attributes JSONB` = 產業變動欄位**；語義由 `field_metadata` 定義（type/required/options/validation/ui_hints），驅動 `DynamicForm` / `DynamicTable` 與驗證。**加欄位不改 schema、不寫 code**。
- **`status` 值域由 pack 的 flow DSL 定義**（§3.3），不寫死 enum。
- **`assignee_ref` 跨系統參照**技師共享池（不跨庫 FK），派工經 OHS API + Kafka。
- locksmith pack 範例：智慧鎖產業欄位（`brand` / `model` / `serial` / `warranty_mode` / `door_material` / `door_thickness` / `teaching_note`）全數落於 `attributes`，語義由 `field_metadata(pack=locksmith)` 定義。

### 3.2 Vertical Pack 結構與 Manifest

```yaml
pack: locksmith
version: 1.2.0
extends: blue-collar-service@2.x     # 繼承藍領基底 pack（共用預設）
field_metadata: [ {entity: work_order, key: brand, type: enum, options: [...], required: true}, ... ]
flow: ./flow.dsl.json                # 工單+金流狀態機（§3.3）
catalog:  { services: [...], materials: [...], pricing_rules: [...] }
knowledge: { skills: [locksmith-cs-sop, locksmith-product-knowledge], rag_corpus: pgvector://locksmith }
ui_composition: { screens: [ {route: /work-orders, layout: [...component refs...]} ] }   # §3.7
blocks: [ dispatch, quote_approval, onsite_consent, collect_payment, settle, ... ]        # §3.5
```

- Pack 語意版本化；**品牌（租戶）= 裝一個 pack@version + 租戶級覆寫**（價目/SLA/品牌參數）。
- Pack 升級走版本相容流程：field_metadata / flow 的向後相容檢查通過才可發布。
- `blue-collar-service` 基底 pack 提供藍領共用預設，各垂直 `extends` 之，減少重複並餵積木飛輪。

### 3.3 Flow DSL schema（宣告式狀態機）

```json
{
  "flow": "locksmith.work_order", "version": "1.2.0", "initial": "created",
  "states": { "created": {}, "dispatched": {}, "on_site": {}, "quoted": {},
              "approved": {}, "in_progress": {}, "completed": {}, "settled": {}, "cancelled": {} },
  "transitions": [
    {"from":"created","to":"dispatched","on":"assign","guard":"role:dispatcher","do":["block:dispatch"]},
    {"from":"dispatched","to":"on_site","on":"arrive","guard":"role:technician","do":["block:onsite_consent"]},
    {"from":"on_site","to":"in_progress","on":"start","guard":"role:technician"},
    {"from":"on_site","to":"quoted","on":"requote","guard":"role:technician","do":["block:build_quote"]},
    {"from":"quoted","to":"approved","on":"customer_approve","do":["block:quote_approval"]},
    {"from":"approved","to":"in_progress","on":"start","guard":"role:technician"},
    {"from":"in_progress","to":"completed","on":"finish","do":["block:capture_evidence"]},
    {"from":"completed","to":"settled","on":"settle","do":["block:collect_payment","block:settle"]}
  ],
  "sla": [ {"state":"dispatched","due":"PT2H","on_breach":["block:notify_supervisor"]} ]
}
```

> 工單 `created` 的前置（**線上報價已客戶確認**，或急件類別非空）由開單 gate 把守（BR-WO-01），不在 FSM 值域內；`on_site → quoted → approved` 為**現場報價修正輪**——線上估價與現場不符（報錯 / 加價 / 改項）時建 quote v+1 由客戶再確認，無異動則 `on_site → in_progress` 直進。

**DSL 四約束**（皆為第一約束，ADR-P010）：AI 可生成 · 人可編輯 · 引擎可執行 · 可驗證（匯入時檢查積木契約 + 商業不變式）。拖拉 FlowEditor 為薄編輯器，只產出/編修 DSL（🔜 規劃中，Phase 2 疊加）。

### 3.4 引擎執行模型

1. 載入 pack flow → 建狀態機。
2. 收到 action/event → **檢查 guard**（RBAC via Casdoor claim + precondition）→ **執行 block**（block 內跑 primitives）→ **持久化狀態** + **寫 `work_order_events`（事件溯源）** + **發 Kafka 事件** + **掛 SLA timer**（Redis/排程）。
3. **冪等**：event seq + idempotency key；**side-effect 經 outbox 保證**（見 §12）。

**執行後端裁定（設計定論）**：flow DSL 自建（DSL 是皇冠寶石——需 AI 可生成 + 拖拉編輯 + 藍領語義，不外包給 BPMN）；executor 自建輕量實作、**與 DSL 解耦，保留 Temporal 為可替換後端**——工單狀態機多為人驅動的狀態轉移 + SLA + 經 Kafka 的 side-effect，不需 durable/saga 重武器；未來出現長流程/複雜補償再換後端，DSL 不動。

### 3.5 積木契約與雙層積木

```json
{ "block":"dispatch", "kind":"domain",
  "inputs": {"technician_ref":"required","window":"optional"},
  "preconditions": ["wo.status==created","wo.location!=null"],
  "guards": ["role:dispatcher"],
  "effects": ["set assignee_ref","emit dispatch.assigned","kafka:dispatch.assigned"],
  "composed_of": ["primitive:query_technician","primitive:set_field","primitive:emit_event"] }
```

**雙層顆粒度（設計定論）**：對外（拖拉 / AI 編譯）只暴露**粗顆粒 domain block**（派工/技師媒合/到府同意/報價核准/收款/對帳結算/通知/escalation）——老闆看得懂「派工」，看不懂「emit event」，避免拖拉爆炸；內部由**細顆粒 primitives**（發通知/查技師/狀態轉移/寫欄位/外呼）組成，平台團隊以 primitives 組合出新 domain block——這是積木飛輪（ADR-P011）的實作機制。契約嚴謹（inputs/preconditions/guards/effects 明確）是 AI 可安全編譯的前提：匯入時可靜態驗證。

### 3.6 逃生艙（plugin SDK / webhook）

**設計定論**：依風險分流、**拒絕 inline code 節點**（任意執行的安全/維運風險，且 AI 生成難以靜態驗證，違反 DSL 可驗證約束）。

| 場景 | 逃生艙 | 治理 |
|---|---|---|
| 需與核心資料/交易緊耦合的自訂邏輯 | **plugin SDK**：註冊型別安全的自訂 block | 過審 + 版本化 + 進 Block Ontology |
| 只需呼叫品牌自有系統/展示邏輯 | **webhook 外呼**：flow 呼外部 HTTP，邏輯在客戶側 | 最鬆耦合，核心不擔責 |

### 3.7 後台呈現分層（兩層渲染）

- **共用元件庫（核心，不隨產業改）**：`DynamicForm` / `DynamicTable`（吃 field_metadata）· `WorkOrderBoard`（按 flow 狀態的看板）· `DispatchConsole` · `QuotePanel` · `FinancePanel` · `EvidenceViewer` · `CustomerTimeline` · `FlowEditor`（🔜 規劃中）。
- **欄位層 = 配置驅動**：產業欄位透過 `field_metadata` 由 DynamicForm/Table 自動渲染（免 code）。
- **畫面層 = 元件組裝**：`ui_composition` 用元件庫組裝該產業後台畫面 + 少量自訂 panel（垂直逃生艙）→ FDE 第 ④ 配置面（輕前端）。

**FDE 新產業 workflow（4 配置面）**：① field_metadata → ② 知識精煉（skills + RAG 語料）→ ③ flow DSL（DSL-first 手寫 + 選用積木）→ ④ ui_composition → 打包 Vertical Pack@version → 品牌實例化。核心引擎/元件庫/金流軌/RBAC/事件骨幹全不動。

---

## 4. 工單狀態機與生命週期

### 4.1 核心工單狀態機（Flow DSL 值域）

核心值域由 §3.3 的 flow DSL 定義：

```
created → dispatched → on_site → in_progress → completed → settled     ← 主路徑
on_site → quoted → approved → in_progress                              ← 現場報價修正輪（線上報價與現場不符時）
（任一非終態 → cancelled；created 前置＝線上報價已客戶確認或急件，BR-WO-01）
```

`status` 不是資料庫 enum——引擎依 pack flow DSL 驗證每次轉移的 `on` 事件、`guard` 與 block preconditions；換 pack 即換值域，核心 code 不改。

### 4.2 locksmith Vertical Pack 狀態細化

以下為 locksmith pack 對核心狀態機的細粒度設計（pack 級配置，非核心）；凡與 §4.1 核心值域衝突，以 Flow DSL 為準。

**設計原則（pack flow 的骨架）**：

1. **漸進式資料蒐集**——欄位在「自然產生的那一刻」由「知道它的角色」填：線上報價確認（客戶）→ 開單（客服）→ 派工（調度）→ 現場（技師，含現場報價複核）→ 完工回報 → 計費 → 客戶簽收。免責/個資簽名必由客戶本人於 LINE 完成（後台唯讀，代簽無法律效力）；費用明細源自報價（single source of truth）。
2. **問題卡與工單分離**——問題卡屬診斷/分流（三層解決：L1 AI 直接回 / L2 遠端指導〔文字客服 / 小編公司電話回撥，客人可留手機〕/ L3 才現場派工），只有 L3 才開工單，避免假工單淹沒派工佇列。**問題卡採漸進式、分角色、分時間收集，以雙 gate 管控，詳見 §4.6。**
3. **開單最低門檻 3 欄位**：服務地址（必填，AI 草擬卡無地址、客服 HITL 補）+ 聯絡人 + 電話。
4. **四道硬性閘門（block preconditions/guards）**：問題卡完整度 ≥ 0.8 才開單（缺品牌/型號/症狀/急迫度 → 422，主管填原因可 override；此為問題卡 **Gate ① 進料閘**，另有結案時的 **Gate ② 知識閘** 管精煉汲取，見 §4.6）；開單前須有客戶已確認之線上報價（急件 carve-out）、派工須 active 技師；完工需照片 ≥ 3 + 簽名 + 序號；過期報價視同未同意。

**Quote 子狀態機**：`draft → internal_approved → customer_sent → customer_confirmed / rejected / expired`；`rejected|expired → draft` 走 re-version v+1（`supersedes_quote_id` 串鏈）。急件（locked_out / trapped_inside / safety_risk）走 `retrospective_audit_only` 路徑：先施工、onsite 結束後 4 小時內補送事後 audit 報價，客戶 LIFF 確認或紙本簽補完 audit 鏈；逾時告警升級主管。每筆 quote 綁 immutable pricing snapshot（content-addressable hash），已送出報價不重算。

**WorkOrder 硬綁定**：`created` precondition = 客服 1-click 審核通過 AND（`Quote.customer_confirmed` OR 急件 carve-out）；`completed` precondition = 地址非空 AND（`Quote.customer_confirmed` OR 急件已補事後 audit）。AI 永不自行轉工單（見 §6.2）。

**Onsite 三段式（現場加價金額分層）**：

| 加價金額 | 流程 |
|---|---|
| ≤ 500 | 技師自確 → 三件套（客戶簽名 + 照片證據 + audit log）→ 回 `working` |
| 501–2000 | `working → pending_quote_v2`（暫停施工）→ 自動建 Quote v+1 → 客戶 LIFF 確認 → 回 `working` 並更新 `material_used` |
| > 2000 | 同上 + 主管覆核 + 三方協商 |

客戶拒絕 v+1 → `customer_disagreed_partial`：維持原報價完工，差額由三件套吸收，ChangeRequest 進客服 escalate 佇列。LIFF 失敗 fallback：QR code → 紙本簽 + 拍照 + audit。

**Payment / Refund**：`deposit_required → paid → pending（對帳）→ 入帳`；`failed / paid → refund_requested`，退款依責任歸屬 5×3 分層裁決。**取消費 5 階段**（cancelled 轉移的 block effect）：未確認 0 元 / 已派工未出發 0 元 / 出發後收車馬費 / 到場後收車馬費 + 檢測費 / 已施工按比例計收；全階段客服可帶原因覆寫 + audit log；技師發起的取消依平台政策另計。

**Evidence Lifecycle**：`fresh → active → pending_purge → purged`；`legal_hold` 凍結（永久且不可逆，解除須決策變更）；two-phase purge——T0 銷毀加密金鑰 + soft delete，T+30 天硬刪。

### 4.3 SLA 逾時與 breach 動作

SLA 宣告於 flow DSL（如 `{"state":"dispatched","due":"PT2H","on_breach":["block:notify_supervisor"]}`）。引擎於狀態進入時掛 timer（Redis/分散式排程），逾時觸發 breach block（通知主管/升級/擴大派工範圍）。locksmith pack 接單 SLA：一般 10 分鐘 / 急件 5 分鐘（per-brand 可覆寫）；30 分鐘無人接單 → 擴大範圍 + 通知客服。

### 4.4 現場報價修正輪的跨系統發起（ADR-027）

報價 bounded context 在**品牌 api（品牌庫）**，技師身分與工作台在**跨租戶 technician-platform**——修正輪的發起走「**技師平台 command → 品牌 api 權威**」邊界（完整決策見 [../14_ADR/ADR-027](../14_ADR/ADR-027_現場報價修正發起邊界_技師平台command_品牌api權威.md)）：

```mermaid
sequenceDiagram
    autonumber
    participant T as 技師（師傅 web）
    participant TP as tech-api（技師平台）
    participant BA as 品牌 api（報價引擎）
    participant C as 客戶（LINE/LIFF）
    T->>TP: 發起修正請求（事由：估價誤差/加價/改項 + 項目 diff，不含金額）
    TP->>TP: 驗 assignee_ref＝本人 + 工單 on_site/in_progress
    TP->>BA: POST /internal/requote-requests（tenant 路由 + S2S 認證 + request_id 冪等）
    BA->>BA: 定價引擎依 diff 計算 → 建 quote v+1（supersedes 串鏈 + 新 snapshot_hash）
    BA->>BA: 分層核可（減價/同額直送；加價 501-2000 小編 / >2000 主管）
    BA->>C: LIFF 推送修正報價（fallback QR / 紙本）
    C->>BA: 確認 v+1 → 工單 on_site → quoted → approved
    BA-->>TP: 狀態經工單投影回技師工作台（Phase 1 OHS 查詢；🔜 Phase 3 Kafka）
```

**硬規則**：技師端**零定價權**（只提交 diff，金額一律品牌引擎算）；技師平台**永不寫品牌庫**；保固 / 建案案件自動送出由品牌端 403（BR-QUOTE-03）；通道故障降級＝技師電話回報、小編後台代發（audit 標 `initiated_via=cs_fallback`）。

### 4.5 急件 carve-out 事後補審引擎（🔜 規劃中——本節為補齊設計）

現況支援度：急件 4 類判定（agent 決策樹）、`urgency` 欄位、接單 SLA 5 分鐘**已設計**；但 **4h 補審 timer、補審佇列、事後確認鏈在系統中不存在**，依本節補齊（宿主：品牌 api）：

1. **開單**：小編急件開單，`emergency_class` 必填寫入工單；開單 gate 免事前報價（BR-WO-01 carve-out），audit 記 `emergency_bypass`。
2. **派工**：急件優先推播，SLA 5 分鐘（§4.3 既有機制）。
3. **補審 timer**：onsite 結束事件觸發建立 `retrospective_audit` 任務，`due = onsite_end + PT4H`，掛用 §4.3 同一 SLA timer 機制。
4. **補審佇列**：派工小編工作台「待補審報價」佇列；補送 `retrospective_audit_only` 報價（急件加價暫定固定額 NTD 1500 `[待確認]`，SQL seed URG-01 待業主定案）→ 客戶 LIFF 事後確認 / 紙本簽 + 拍照。
5. **逾時升級**：逾 4h → audit alert 升主管 review；同品牌連續 ≥ 3 次逾時 → 自動開 ChangeRequest 進主管佇列（BR-WO-04）。
6. **結案 gate**：`retrospective_quote_audit_complete` 為急件結案 422 硬閘之一（04_SRS §2.2.4 既有）。

### 4.6 問題卡（診斷卡）漸進式生命週期與雙 gate（🔜 規劃中——本節為補齊設計）

**定位**：問題卡是「一次客訴的結構化診斷紀錄」，屬診斷/分流層（§4.2.2），是**派工**與**知識精煉**（§9）的共同上游。它**不是一步填完**——AI 起手整理對話可能有遺漏、L3 根因要現場維修後才知道——故採**漸進式、分角色、分時間**收集（對齊 §4.2.1），並以**兩道語意不同的 gate** 分管「能不能派工」與「能不能沉澱知識」。

**生命週期狀態機**：

```
[AI 起草 draft] ──① 進料 gate──▶ [已分流 triaged] ──┬─ L1 ──────────────────▶ [已處理 handled]
   (AI 抽對話,可能缺)  ⤴ 小編補缺                     ├─ L2 ─(文字客服/電話回撥)─▶ [已處理 handled]
                                                       └─ L3 ─▶ 開工單→派工→現場完工→(小編/技師補寫)─▶ [已處理]
[已處理] ──② 知識 gate──▶ [知識完整 knowledge_ready] ──▶ 精煉服務汲取（§9）
   └─ 未過②：進「待補知識佇列」，事後補 ◀────────────────┘
```

`status` 業務值域（對齊 §4.1 / 04_SRS）：`draft(=incomplete) → triaged → handled(resolved)`；另加旗標 `knowledge_ready`（②gate 通過）與既有 `converted_at`（轉工單）。**「operational 已處理」與「知識完整」是兩件事**——卡可先結案，知識欄事後補。

**三層分流細化**（refine §4.2.2）：

| 層級 | 處理 | `resolution_channel` | 處置由誰寫 | 開工單 |
|---|---|---|---|---|
| L1 | AI 直接回 | `ai_auto` | AI 自動 | ✗ |
| L2a | 真人文字客服 | `line_text_cs` | 文字客服 | ✗ |
| L2b | 小編公司電話回撥（客人留手機） | `phone_callback` | 小編（通話後補寫） | ✗ |
| L3 | 現場派工維修 | `onsite` | 技師完工 → 小編/技師補寫 | ✓（過 §4.2.4 四閘） |

**Gate ① 進料閘（派工/處理前）**——即 §4.2.4 完整度閘，細化必填集，以 `intake_completeness` 計分：

| 必填 | 說明 |
|---|---|
| `contact_phone` | 任何真人跟進（L2b 回撥 / L3）皆需 |
| `brand` + `model` | 產品識別（AI 抽不到 → 小編確認，或標「已確認未知」） |
| `failure_mode` | 失效模式分類（enum） |
| `triage_tier` | L1/L2/L3 分流決策 |
| `service_address` | **條件必填：僅 L3**（既有 HITL 補址） |

未過①：AI 起草缺欄記 `ai_missing_fields` → 小編佇列補齊才放行。

**Gate ② 知識閘（結案/精煉前，可事後補）**——RMA/QA 失效分析 spine，以 `resolution_completeness` 計分：

| 必填 | 說明 |
|---|---|
| `root_cause` + `root_cause_category` | 根因（無根因＝軼事非知識） |
| `corrective_action` | 矯正措施 / 處置步驟（SOP payload） |
| `verification` | 是否驗證修復（8D D6；未驗證的解法會污染知識庫） |
| `disposition` | 處置分類 enum：換貨 / 維修 / 軟體更新 / 誤操作教育 / 現場服務 / NTF 無法重現 |
| `resolution_channel` + `resolved_by` | 哪個管道 / 誰解的 |
| `firmware_version` / `serial` | **L3 額外**——技師現場採集，RMA 批次瑕疵關聯 |

未過②不阻擋 operational 結案，但**擋「進精煉」**；卡進「待補知識佇列」提示小編/技師補完。精煉服務（§9 汲取層）**只汲取 `knowledge_ready=true`** 的卡。

**兩個下游各取所需**：派工只看 Gate ①（快速放行、防假工單）；精煉只吃 Gate ②（要 spine 完整）——互不綁架，也承接「沒辦法一步到位」的現實時序。

**Schema 調整（🔜 動 `problem_cards`，須走 CIA + migration；18_DB_Design 同步）**：
- 拆 `completeness_score` → `intake_completeness` / `resolution_completeness`（一個分數不能同時服務兩道 gate）。
- 新增失效分析 spine：`root_cause`、`root_cause_category`、`corrective_action`、`verification`、`disposition`、`resolution_channel`、`resolved_by`、`firmware_version`、`serial`、`knowledge_ready`。
- 補 `tenant_id`（現況靠 `conversation_id` 間接推；精煉為跨租戶共享池，隔離需直接租戶欄）。
- 廢除舊 harness 遺留死欄（LockCore 已不寫、且與 L1/L2/L3 分流概念混淆）：`attempts`（L5 ResolutionAttempt）、`diagnosis_status`（PDCA）、`is_novel`、`card_id`、`domain_attributes`。

**開放決策 [待裁決]**：
- (a) Gate ② 是否硬擋「最終結案」，還是只擋「精煉汲取」（先結案、知識非同步補）。
- (b) `firmware_version` / `serial` 由技師 app 現場採集的來源與必填強度。
- (c)「待補知識佇列」的 SLA 與逾時升級（比照 §4.3 timer）。
- (d) 跨租戶 / License：未購精煉 License 的租戶其卡是否進共享語料、產出 SOP 歸品牌私有或回饋共享（連 §9 bronze-only 治理與 ADR-018）。

---

## 5. agent 子系統詳細設計（LockCore LINE Bot AI 客服）

### 5.1 L3 元件

agent 為單一 Python 進程（aiohttp），核心引擎 LockCore 採「三層引擎 + 供應商 + 工具 + 記憶 + 知識」結構：

| 元件 | 檔案 | 職責 |
|---|---|---|
| line_gateway | `lockcore/channels/line_gateway.py` | `POST /callback` 驗簽（X-Line-Signature）、訊息型別分派、Reply、`/internal/*` 旁路橋接 |
| AgentLoop | `lockcore/agent/loop.py` | 產品層 Turn 狀態機（8 態），一個 webhook = 一個 turn |
| ContextBuilder | `lockcore/agent/context.py` | 組 system prompt：identity → Customer Memory → always-skills → skill 摘要（漸進式揭露）|
| AgentRunner | `lockcore/agent/runner.py` | 通用 tool-using LLM 迴圈（無產品層概念），context governance 每輪執行 |
| LiteLLMProvider + FallbackProvider | `lockcore/providers/` | Model Orchestration Layer：model 字串路由多家（`vertex_ai/` / `gemini/` / `claude-*` / `gpt-4o`…）；多供應商 failover |
| ToolRegistry | `lockcore/agent/tools/` | 工具白名單 `CS_TOOL_ALLOWLIST` 6 項：`read_file / list_dir / find_files / grep / web_search / transfer_to_human` |
| MemoryManager + Store | `lockcore/agent/user_memory/` | per-user 記憶：BUILD 注入 / SAVE 寫回；Postgres schema `agent.*`（pg_trgm/GIN）；讀寫必帶 tenant+user_id，缺則 raise（default deny）|
| EscalationStore | `lockcore/agent/user_memory/escalation.py` | 轉真人稽核紀錄（含 facts_snapshot JSON）|
| SkillsLoader + 2 builtin skills | `lockcore/skills/` | Agent Skills 標準（SKILL.md + references）：`locksmith-product-knowledge`（事實層）+ `locksmith-cs-sop`（行為層，紅線決策樹）|

長尾逐型號事實檢索走 **RAG-via-MCP** 查 pgvector 唯一事實語料（`manual_chunks` / `case_entries`）；skill 只留行為 + 精選事實（🔜 規劃中，語義層依 agent ADR-004 分階段建置，filesystem references 於品質 gate 通過前為 fallback）。

### 5.2 Turn 狀態機

```mermaid
stateDiagram-v2
    [*] --> RESTORE
    RESTORE --> COMPACT: 載入 session 歷史
    COMPACT --> COMMAND: 視需要壓縮上下文
    COMMAND --> BUILD: 非指令訊息
    BUILD --> RUN: 組 initial messages（注入 Customer Memory + skill）
    RUN --> SAVE: AgentRunner 迴圈完成（tool-using LLM）
    SAVE --> RESPOND: 存 session + record_turn（記憶寫回，try/except 包覆）
    RESPOND --> DONE: 產生回覆文字
    DONE --> [*]
```

記憶寫入以 try/except 包覆——記憶失敗絕不讓 turn 失敗。

### 5.3 關鍵序列

**LINE 訊息 → Turn → 回覆**：LINE `POST /callback` → 驗簽（失敗 400）→ 查 api `GET /internal/conversations/handover-state`（阻塞 5s、fail-soft；人工接管中則 AI 靜默）→ `AgentLoop._process_message` 跑 Turn → BUILD 注入 `<memory>` 客戶事實 + skill 摘要 → AgentRunner 有界迴圈（chat → tool_calls → 執行工具）→ SAVE 記憶寫回 → 回覆前 `POST /internal/conversations/ingest`（fire-and-forget 20s）→ sentinel/空回覆轉友善話術、單則 > 4900 字截斷 → `reply_message`。

**Escalation 轉真人（含兜底）**：cs-sop 紅線（金錢/要真人/急件/派工）→ LLM 呼叫 `transfer_to_human(reason, brand, model, symptom)` → 拉 per-user facts + 偵測 `is_explicit` → 寫 EscalationStore → 回核對表單（原封不動回覆客戶）。**兜底路徑**：LLM 生成「已為您安排師傅」話術卻未呼叫工具時，gateway 偵測承諾話術 + 本輪 escalation 未新增 → deterministic 補抽品牌/型號/症狀/手機 → 程式補一筆 escalation。兩路皆 `POST /internal/escalations/ingest` → api 建 AI 草擬問題卡（→ 客服 → 工單 → 派工）。

### 5.4 錯誤處理與重試

| 機制 | 設計 |
|---|---|
| 有界重試 | empty-retry 上限 2 / length-recovery 上限 3 / injection guard 3 次·5 循環 |
| 邊界分類 | SSRF / workspace 邊界違規由 Runner 分類攔截 |
| context governance | 每輪執行：microcompact、tool-result budget、snip history |
| 供應商失敗 | LiteLLMProvider 失敗不 raise → `[litellm error]` sentinel → LINE 層轉友善話術；FallbackProvider 多供應商 failover（ADR-P008）|
| 調用效率 | 快取 / 批次 / 平行工具呼叫 / 逾時重試集中於 Model Orchestration Layer；LLM 逾時上限 `NANOBOT_LLM_TIMEOUT_S`（預設 300s）|
| 旁路 fail-soft | `/internal/*` 持久化與接管查詢失敗只 log，絕不阻斷客人回覆 |

---

## 6. api 子系統詳細設計（派工營運控制平面）

### 6.1 L3 元件（分層 + 守衛鏈）

```mermaid
flowchart TD
    MAIN["main.py — FastAPI app<br/>API_SURFACE 塑形（dispatch/tech/platform）"]
    subgraph MW["Middleware（先進後出）"]
        CORS["CORSMiddleware"] --> REQID["RequestIdMiddleware"] --> DEP["DeprecationMiddleware"]
    end
    subgraph PRES["Presentation（routers/）"]
        R_V2["tenant-scoped routers<br/>/tenants/{tid}/…"]
        R_WS["WebSocket 端點 /realtime/*（10 頻道）"]
        R_INT["internal_ingest.py /internal/*（4 端點）"]
    end
    subgraph GUARD["守衛鏈（core/deps.py）"]
        G1["get_current_user<br/>驗 Bearer + jti 撤銷 + 安全狀態"]
        G2["require_tenant<br/>X-Tenant-ID 比對 claim"]
        G3["role_required(*roles)<br/>deny-by-default enforce"]
        G4["require_platform_admin"]
        G5["require_internal_token<br/>fail-closed（hmac 常數時間比對）"]
    end
    subgraph APP["Service Layer（services/）"]
        SVC["work_order / dispatch / invoice / settlement /<br/>conversation / problem_card / …"]
        LINEOUT["line_push_service + outbox worker（fail-soft + retry）"]
    end
    subgraph CORE["Core / Infra"]
        DB["core/db.py — 連線池 + 交易邊界"]
        ERR["core/errors.py — RFC7807 problem+json"]
        MODELS["Pydantic v2 — ApiResponseGeneric / CursorPage"]
    end
    subgraph RTL["即時與事件層"]
        REDIS["Redis pub/sub fan-out（WS 推播）"]
        KAFKA["Kafka producer/consumer（workorder.* / dispatch.* / commission.*）"]
        SCHED["分散式排程（SLA / GDPR 硬刪 / 自動結案 / LINE outbox）"]
    end
    MAIN --> MW --> PRES
    R_V2 --> G3 --> G2 --> G1
    R_INT --> G5
    R_WS --> REDIS
    R_V2 --> SVC --> DB
    SVC --> REDIS
    SVC --> KAFKA
    SVC --> LINEOUT
    SCHED --> SVC
    R_V2 -.-> ERR
```

- **守衛鏈組合**：`role_required → require_tenant → get_current_user`（層層 await）；平台端走 `require_platform_admin`（不收 X-Tenant-ID，跨品牌視角）；服務間走 `require_internal_token`（fail-closed）。授權採 **deny-by-default enforce**，逐端點掛 `role_required`；RBAC 矩陣全表歸 [13_Security_Architecture](./13_Security_Architecture.md)。
- **回應信封**：成功 `ApiResponseGeneric` / `CursorPage`；錯誤 RFC7807 problem+json superset。
- **部署塑形**：同一 codebase 靠 `API_SURFACE` 塑形部署面；塑形是路由過濾，非安全邊界——隔離押在每端點 RBAC。

### 6.2 關鍵序列

**工單建立 + WS 推播**：web `POST /tenants/{tid}/work-orders`（Bearer + X-Tenant-ID + Idempotency-Key）→ 守衛鏈（角色不符 403 RFC7807）→ `work_order_service.create_work_order` → INSERT `work_orders` → publish 至 Redis 頻道 `/realtime/dispatch-queue` → 所有實例的訂閱者收到 → 回 `201 ApiResponseGeneric{data}`。

**WS 頻道授權**：瀏覽器 `WSS /realtime/pool/{tech_id}?access_token=…&tenant_id=…`（瀏覽器 WS 不支援 custom header → query 參數）→ `verify_ws_token`（decode + type==access + jti 撤銷 + tenant 一致，失敗 close 1008）→ `authorize_channel`（tech_id == sub 或 role ∈ {admin, ops_manager}，失敗 close 1008）→ accept + subscribe → 單向 send_json 推播直到 disconnect。

**agent internal ingest**：agent `POST /internal/conversations/ingest`（X-Internal-Token）→ `require_internal_token`：token 未設 → 503 fail-closed；不符 → 401 → `_resolve_tenant_id` → 旁路持久化 conversations/messages 或 escalation 建 AI 草擬問題卡（`source='ai_line'`）。**AI 永不自轉工單**——confirm/convert 一律走客服認證端點。

**LINE 入站單一路徑**：LINE webhook 唯一入站為 agent `/callback`；postback 由 agent fan-out 至 api `/internal/*`。api 不設 LINE 入站端點；出站 Push 走 LINE outbox worker。

### 6.3 即時與背景

| 機制 | 設計 | 交付期 |
|---|---|---|
| WS 推播 | Redis pub/sub fan-out——事件跨實例廣播，支援水平擴展 | 🔜 Phase 2 導入（ADR-P007）|
| 事件骨幹 | Kafka producer/consumer：`workorder.*` / `dispatch.*` / `commission.accrued` 等（§11.1）| 🔜 Phase 2 導入 |
| 背景任務 | 分散式排程 + 分散式鎖（SLA 掃描 / GDPR 硬刪 / 自動結案 / canary）| 🔜 Phase 2 導入 |
| DB 連線 | psycopg3 連線池 + 顯式交易邊界；讀寫分離（清單/查詢走 replica）| 🔜 Phase 2 導入 |
| LINE 推播 | outbox worker：fail-soft + retry，推播失敗不阻斷業務寫入 | Phase 1 |

### 6.4 錯誤處理

- **錯誤信封**：RFC7807 problem+json（`core/errors.py` 全域 exception handler）。
- **冪等**：所有 mutation 端點收 `Idempotency-Key`，`core/idempotency.py` 重放（IdempotencyReplay）。
- **outbox 保證**：DB 寫入與事件/推播 side-effect 以 outbox 分離，worker 重試至成功。
- **服務間認證 fail-closed**：`require_internal_token` 以 `hmac.compare_digest` 常數時間比對；未配置直接 503。

---

## 7. technician-platform 子系統詳細設計（跨租戶技師共享池）

### 7.1 L3 元件

獨立系統 + 自有庫 `lock_tech`（技師身分/技能/品牌授權/認證/排班/評分/佣金 profile 的單一真相）；含獨立師傅 web（上線註冊 / 工作台 / 技師後台，跨品牌共用，不進品牌 bundle）。

| 元件群 | 內容 |
|---|---|
| OHS API routers | `GET /technicians` · `POST /technicians:match` · 排班/認證查詢（各品牌 api 消費）|
| self-service routers | 上線註冊 / profile / 技能授權 / 認證上傳 / 排班設定 / 工作台 |
| WS 端點 | `/realtime/pool/{tech_id}` 師傅即時推播（Redis pub/sub 撐）[待確認：推播歸屬技師平台或品牌 api] |
| 守衛鏈 | Casdoor OIDC bearer 驗證（技師 = 跨租戶身分）→ role enforce（deny-by-default）；OHS 服務憑證 [待確認：OIDC client-credentials vs internal token] |
| Service 層 | `technician_service`（身分/技能/授權）· `matching_service`（技能/地區/授權/可用性排序）· `schedule_service` · `certification/kyc_service`（Fernet 加密敏感欄位）· `rating_service` / `commission_settlement_service` |
| 事件層 | producer：`technician.{registered,certified,brand_authorized,availability_changed,assignment_accepted,rating_updated}`；consumer：`dispatch.assigned` → 更新排班/工作量、`workorder.completed` → 評分/佣金基礎、`settlement.generated` → statement；read-model：技師工單投影 |

**品牌不直連技師庫**——整合三路：① 品牌 api → OHS API（同步查詢/媒合）；② 技師平台 → Kafka 發布技師狀態事件（單一真相的最終一致廣播）；③ 技師平台 ← Kafka 訂閱派工/工單事件。品牌側以 ACL adapter 包裝 OHS 呼叫，技師領域模型不外溢。

### 7.2 關鍵序列

**派工媒合（同步 OHS + 非同步 Kafka）**：

```mermaid
sequenceDiagram
    participant BAPI as 品牌 api（ACL adapter）
    participant OHS as 技師平台 OHS API
    participant MATCH as matching_service
    participant TDB as lock_tech
    participant KAFKA as Kafka
    participant WS as 師傅即時推播
    participant TECH as 師傅工作台

    BAPI->>OHS: POST /technicians:match（OHS 服務憑證）
    OHS->>MATCH: match(skill, region, brand_auth, availability)
    MATCH->>TDB: 查技能/品牌授權/認證有效/排班可用
    MATCH-->>OHS: 排序候選（評分/距離/工作量）
    OHS-->>BAPI: 候選清單（OHS 契約 DTO → 轉品牌領域模型）
    BAPI->>KAFKA: publish dispatch.assigned
    KAFKA->>OHS: consume → 更新排班/工作量 + 工單投影
    OHS->>WS: 推播「新派工到手」
    WS->>TECH: 即時通知
    TECH->>OHS: 接單 / 拒單
    OHS->>KAFKA: publish technician.assignment_accepted / rejected
    KAFKA->>BAPI: consume → 品牌 api 更新工單狀態（最終一致）
```

同步 OHS 只做「查詢/媒合」（讀、低延遲）；指派/接單走 Kafka 事件（寫、解耦、可重播）。OHS 短暫不可用時品牌側 ACL adapter 降級策略 [待確認：快取上次候選 / 排隊重試]。

**上線註冊 + 認證准入**：師傅 → 技師 web → Casdoor OIDC 授權碼流建立跨租戶身分（role=technician）→ 建 profile（`users/technicians/technician_skill`）→ publish `technician.registered` → 上傳 KYC/認證（Fernet 加密存 `technician_kyc/certification`）→ 人工審核（准入閘門）→ 認證生效 + 品牌授權 → publish `technician.certified` + `technician.brand_authorized` → 各品牌 api 訂閱更新可派工技師投影。通過准入後才進入媒合候選集。

**技師狀態廣播**：技師平台 service 寫入 `lock_tech` 單一真相（停權/認證撤銷/評分更新）→ producer 發 `technician.*` → 各品牌獨立訂閱更新本地投影/派工可用性；事件持久可重播，品牌重啟/新接入可補投影。

### 7.3 佣金 Billing/Settlement 分離 + 工單 CQRS 投影（ADR-P014）

technician-platform = **品牌事件的 CQRS 消費端**：命令端（工單/計費）真相在品牌庫，查詢端（技師視角/結算）在技師平台，共用同一 Kafka 事件骨幹。

- **Billing（品牌庫）**：per-job 佣金明細計算（依賴工單金額/料件/完工，皆品牌側資料）→ 發 `commission.accrued` 事件。計費引擎留品牌，貼近資料源、避免跨庫依賴。
- **Settlement（技師平台）**：訂閱各品牌 `commission.accrued` → 技師**跨品牌單一對帳 / statement / payout** 主體（`technician_statement` / `technician_payout_rule` 落於技師平台）。最終一致性以期末對帳閘門（reconcile 品牌計費 vs 技師平台彙總）收斂。
- **工單可見性 = Kafka-fed CQRS 投影**：品牌 api 發 `workorder.{dispatched,updated,completed}` → 技師平台維護「技師視角工單投影」（**欄位最小化**：摘要/地址/狀態/時窗/金額/該技師派工，不整包複製品牌敏感資料）→ 師傅工作台讀投影，**不直連品牌庫**（守 per-brand 物理隔離）。

---

## 8. web 子系統詳細設計（多站前端）

### 8.1 L3 元件

單一 Next.js codebase（App Router、全 client component 的 SPA），build-time `APP_MODE` 塑出多個 portal；無 BFF、無自有 DB，瀏覽器直連 api。

| 元件 | 檔案 | 職責 |
|---|---|---|
| AuthGuard | `src/components/layout/AuthGuard.tsx` | 掛 root layout 的 client-side 路由守衛：crossModeRedirect → token 檢查 → role gate |
| appMode gate | `src/lib/appMode.ts` | APP_MODE 分站：判定當前 build 是否服務此路徑，否則導向對方 portal |
| rolePolicy | `src/lib/rolePolicy.ts` | route→roles longest-prefix 政策表（UX 層；真正授權在 api `role_required`）|
| api client | `src/lib/api.ts` | 統一 fetch：Bearer / X-Tenant-ID / Idempotency-Key 注入、401 refresh（依 role 分流端點）、錯誤信封解析 |
| cache | `src/lib/cache.ts` | GET 共享 in-flight + 30s staleTime；mutation 後 `cacheInvalidate("GET:")` 廣域清除 |
| realtime | `src/lib/realtime.ts` | WS 訂閱層：一 channel 一 socket、backoff 重連、未配置靜默降級 |
| 型別 | `types/api.generated.ts` | 由 `openapi.yaml` 生成，防契約漂移 |

### 8.2 APP_MODE 分站機制

`NEXT_PUBLIC_APP_MODE` 於 Docker build ARG 烤入 bundle（runtime 不可改）；值域 `all | dispatch | platform | landing`（品牌 bundle 前端只含 dispatch；師傅端 web 歸 technician-platform，見 §7）。

| mode | 允許路由 | 其餘導向 |
|---|---|---|
| all（預設）| 全部（gate 恆 null）| — |
| dispatch | 品牌後台全部 | `/`→`/login`；`/platform/*`→`/login`；師傅路由→技師平台 portal |
| platform | 只 `/platform/*` | `/platform/login` |
| landing | 只 `/` | `DISPATCH_PORTAL_URL + pathname` |

跨端導向以 `PEER/TECH/DISPATCH/PLATFORM_PORTAL_URL` env 集中解析；dispatch build 特意擋 `/tech-register`，避免在品牌庫產生平台 console 看不到的幽靈師傅。

### 8.3 關鍵序列

**登入 gate 三段**：開啟路徑 → AuthGuard 掛載 → ① `crossModeRedirect(pathname)`（不服務則導向對方 portal）→ ② token 檢查（無 token 且非公開頁 → `/login`）→ ③ `rolePolicy.canAccessRoute`（無權導該角色安全落點）→ 渲染頁面 → `api.get` 帶 Bearer/X-Tenant-ID，真正授權由後端把關。認證採 Casdoor OIDC 授權碼流 + token 安全儲存（httpOnly cookie），未列路由 deny-by-default（政策細節歸 [13_Security_Architecture](./13_Security_Architecture.md)）。

**分頁抓取 + GET cache**：`usePaginatedFetch` → `api.get` → cache key = `GET:{fullUrl}:{tenant}` → 命中（< 30s staleTime）回共享 in-flight/快取；miss → fetch → 401 則 refresh 後重放 → `{data, meta}` 信封寫入快取。mutation 後 caller 以 `cacheInvalidate("GET:")` 廣域清除。

**WS 訂閱（backoff + 靜默降級）**：`REALTIME_BASE_URL` 未配置 → `status=disabled`，不訂閱、頁面照常 fetch（**靜默降級，不 crash**）；有值 → `?access_token=JWT&tenant_id=TID` 連線 → onmessage → JSON.parse → callback；onclose/onerror → scheduleReconnect（1s→2s→5s→10s→30s）；卸載 close(1000)。

---

## 9. knowledge-refinery 子系統詳細設計（知識精煉 + 審核 UI）

### 9.1 L3 元件

License 開通的附加系統（集中共用，非 per-brand bundle）：長駐精煉服務 + 審核 web UI（Casdoor OIDC）。

| 元件 | 職責 |
|---|---|
| 汲取層 | 兩類輸入：診斷對話（`line_chat` / `problem_cards`，汲取機制 [待確認：api 唯讀端點 / 批次匯出 / 事件]）+ 產品素材（YouTube / 影片 / 官網 / 手冊）|
| raw_to_bronze | ASR（Whisper）/ Vision LLM / bs4+markdownify 清洗轉錄 |
| bronze_to_silver | 冪等性檢查 → LLM 語音糾錯 + 去冗 + 語意切塊 → 產 JSON array → **Python 強制覆寫 `source`/`source_type`（provenance 防幻覺）** |
| 提煉分流器 | LLM 依第一性原則分流：「定義 agent 怎麼行為」→ 行為/精選；「被查找的事實」→ 事實 |
| Draft Queue | 提煉產物落地前的審核佇列（事實 draft + provenance；行為 draft + diff vs 既有 skill）|
| 審核 UI backend | draft 狀態機（§9.2）+ diff 呈現；與 AI Onboarding Compiler 共用 HITL 審核骨架（ADR-P011 孿生）|
| Publisher | 核可後才落地：事實 → `embed()`（text-embedding-004，768 維）chunk+embed 灌 pgvector `manual_chunks` / `case_entries`（帶 tenant/brand 過濾欄）；行為 → append-only git 寫入 lockcore `references/{Brand}/{Model}.md` + SKILL.md |

`manual_chunks` / `case_entries` 的 schema 由 api 資料層擁有；本系統僅為寫入方。

### 9.2 審核狀態機

```
draft → pending → approved（Publisher 落地）
                → rejected（留 audit）
                → re-refine（退回提煉分流器重煉）
```

**HITL 硬 gate**：任何產物核可前絕不寫入 pgvector / skill；skill 更新 append-only 只增不刪改，git 可完整回溯。

### 9.3 關鍵序列與 bronze-only 治理

**診斷 → 精煉 → 審核 → 落地**：素材 + 診斷對話 → raw_to_bronze → bronze（★ sourcing 真相源）→ bronze_to_silver（Python 覆寫 provenance）→ 提煉分流（事實 / 行為）→ Draft Queue → 審核者（Casdoor OIDC）看 diff → 核可（事實）→ embed → 灌 pgvector；核可（行為）→ append-only 更新 skill；退回 → re-refine；拒絕 → 留 audit。下游：agent 經 RAG-via-MCP 查語料 + 載入 skill；api 後台查同一份語料（唯一事實語料，單一真相）。

**Bronze-only Sourcing（不變鐵律）**：知識內容嚴格源自 bronze 層（YouTube 字幕 / website / video transcript）；**PDF（GDrive）不可信——只引 URL、不抄內容**。治理落點：Python 覆寫 provenance、Publisher 灌注前校驗 draft `source` 屬 bronze 白名單、CI 做 references ↔ pgvector 同源檢查。

---

## 10. AI Onboarding Compiler 與 Block Ontology（🔜 規劃中，ADR-P011 / Phase 5）

- **AI Onboarding Compiler**：輸入客戶 tacit 流程（SOP 文件 / 訪談 / 舊系統匯出）→ AI 對映 Block Ontology 詞彙 → 產出 **draft flow DSL** + 標記缺口（需新積木的步驟）→ 拖拉 UI 呈現 → **人審後匯入**。碰**金流 / 派工 / 同意書**的流程必過人審，不盲匯入。
- **Block Ontology（積木飛輪）**：每落地一產業 → 發現新積木 → 進庫（版本化 + 治理 + 向後相容）；積木庫 = 累積的藍領營運本體論，越後面的產業越多是重組 → onboarding 越快。冷啟動誠實原則：頭 2–3 個產業積木手工建、AI 命中率低，不對外過早承諾「AI 一鍵匯入」。
- **HITL 孿生**：與 knowledge-refinery 共用 draft → 人審 diff → 落地的審核 UI 骨架（一煉知識、一煉流程）。
- **依賴序**：嚴格後於 flow DSL 穩定（§3 Phase 1）——Phase 0 DSL + 引擎 → Phase 1 Block Ontology v0（locksmith 手工積木）→ Phase 2 Compiler MVP → Phase 3 飛輪運轉、量測 AI 命中率。

---

## 11. 跨系統整合設計

### 11.1 事件骨幹（Kafka topic 命名）

| Topic 前綴 | 事件 | 生產者 → 消費者 |
|---|---|---|
| `technician.*` | `registered / certified / brand_authorized / availability_changed / assignment_accepted / rejected / rating_updated / certification_revoked` | technician-platform → 各品牌 api |
| `dispatch.*` | `assigned` | 品牌 api → technician-platform |
| `workorder.*` | `dispatched / updated / completed` | 品牌 api → technician-platform（CQRS 投影）|
| `commission.*` | `accrued` | 品牌 api（Billing）→ technician-platform（Settlement）|
| `settlement.*` | `generated` | technician-platform → 品牌 api / statement |

事件 schema 契約與版本治理見 [17_AsyncAPI](./17_AsyncAPI.yaml)；schema registry + consumer-driven contract test 防破壞。

### 11.2 同步整合

| 路徑 | 協議 | 認證 |
|---|---|---|
| 品牌 api → technician-platform | OHS API（查詢/媒合/排班/認證）| OHS 服務憑證 [待確認] |
| agent → api | `/internal/*` 4 端點（conversations ingest / handover-state / escalations ingest / quotes respond）| X-Internal-Token（agent 側 fail-soft / api 側 fail-closed）|
| web → api | REST + WS（`ApiResponseGeneric` 信封）| Casdoor OIDC Bearer + X-Tenant-ID |
| knowledge-refinery → 品牌庫 | Publisher 灌事實語料（psycopg3）| 服務帳號；schema 由 api 擁有 |
| LINE → agent | webhook `POST /callback`（唯一入站；postback fan-out → `/internal/*`）| X-Line-Signature 驗簽 |

### 11.3 冪等 / 重播 / 最終一致原則

- **同步寫入冪等**：mutation 端點一律收 `Idempotency-Key`；引擎轉移以 event seq 去重。
- **事件可重播**：Kafka 事件持久化；消費端投影可由重播重建（品牌重啟 / 新品牌接入補投影）。
- **最終一致 + 對帳閘門**：跨系統狀態（工單投影 / 佣金彙總）接受事件延遲；金流結算以期末 reconcile 收斂差異。
- **跨租戶隔離平台鎖死**：MCP-RAG 與 DB 查詢層強制 tenant ACL，非應用層自律。

---

## 12. 錯誤處理與韌性通則

| 系統 | 機制 | 摘要 |
|---|---|---|
| agent | 有界重試 + sentinel | empty-retry(2) / length-recovery(3) / injection(3/5cy)；LLM 失敗回 sentinel 轉友善話術；旁路 fail-soft |
| api | RFC7807 + outbox + idempotency | 統一錯誤信封；side-effect 走 outbox；Idempotency-Key 重放；internal token fail-closed |
| 工單引擎 | 冪等 + outbox | event seq + idempotency key；side-effect（通知/事件）經 outbox 保證送達 |
| technician-platform | 事件重播 + 對帳 | Kafka 可重播補投影；Settlement 期末對帳閘門 |
| web | 靜默降級 | WS/SSE 未配置或斷線 → disabled/backoff，頁面照常以 REST 運作 |
| knowledge-refinery | 冪等 + provenance 覆寫 | bronze→silver 冪等性檢查；Python 強制覆寫 provenance 防 LLM 幻覺；HITL 硬 gate |

**設計層降級原則**（操作步驟歸 [24_Runbook](./24_Runbook.md)）：

1. **kill switch 三層**：AI 回覆層（AI 靜默、全量轉真人）→ 通道層（暫停 LINE 出站推播）→ 系統層（服務下線、fail handoff）。任一層啟動皆保「案子不蒸發」——escalation 兜底照寫、outbox 暫存待送。
2. **fail-soft 優先於 fail-closed**，惟安全邊界（internal token、tenant 隔離、HITL gate）恆 fail-closed。
3. **每則客戶訊息都有回覆**：任何內部失敗最終收斂為友善話術，不外洩錯誤細節。

---

## 13. 追溯表（設計元件 → ADR / 上位需求）

| 本 SDS 設計元件 | 章節 | 依據 |
|---|---|---|
| 核心 vs 配置分層、FDE 4 配置面、Vertical Pack | §2.1, §3.2, §3.7 | ADR-P009 |
| Flow DSL + 積木契約 + DSL-first + 逃生艙 | §3.3–§3.6, §4.1 | ADR-P010 + 平台 SDS §9 三子決策裁定 |
| AI Onboarding Compiler + Block Ontology + HITL | §10 | ADR-P011 |
| Model Orchestration Layer（供應商=配置、fallback）| §5.1, §5.4 | ADR-P008、agent ADR-002 |
| LockCore Turn 狀態機 / Agent Skills / 工具白名單 | §5 | agent ADR-001 / ADR-003 |
| RAG-via-MCP + Skill 行為驅動分工 | §5.1, §9.3 | agent ADR-004 |
| 技師共享池獨立、assignee_ref 不 FK、OHS + Kafka | §3.1, §7 | ADR-P004 |
| Kafka / Redis / 讀寫分離 / 分散式排程 | §6.3, §11 | ADR-P007 |
| 佣金 Billing/Settlement 分離、工單 CQRS 投影 | §7.3 | ADR-P014 |
| 知識精煉獨立服務 + HITL 審核 + 雙產物 | §9 | ADR-P001 |
| Casdoor OIDC / deny-by-default enforce | §6.1, §7.1, §8.3 | ADR-P003 / ADR-P006（正文歸 13_Security）|
| LINE 單一入站（agent /callback）| §6.2, §11.2 | ADR-P012 G-06 方案 A |
| locksmith pack 狀態細化（Quote/WO/Onsite/退款/證據）| §4.2 | system-spec 狀態機 + ARCH-0006 流程設計 |

---

## 附錄：元件 — 檔案路徑對照

| 系統 | 元件 | 路徑 |
|---|---|---|
| agent | Turn 狀態機 / Runner / Context | `agent/lockcore/agent/{loop,runner,context}.py` |
| agent | LLM 供應商層 | `agent/lockcore/providers/{litellm_provider,fallback_provider}.py` |
| agent | 工具（白名單 6 項）| `agent/lockcore/agent/tools/`（filesystem / search / web / transfer）|
| agent | per-user 記憶 + escalation | `agent/lockcore/agent/user_memory/{manager,store,postgres_store,escalation}.py` |
| agent | 知識 skill | `agent/lockcore/skills/locksmith-{product-knowledge,cs-sop}/` |
| agent | LINE 通道 / 啟動點 | `agent/lockcore/channels/line_gateway.py` · `agent/scripts/line_gateway.py` |
| api | 守衛鏈 / 錯誤 / 冪等 / DB | `api/core/{deps,errors,idempotency,db,auth,pii_crypto}.py` |
| api | 路由 / 服務分層 | `api/routers/`（tenant-scoped）· `api/services/`（業務 + SQL）|
| api | 即時 / 背景 worker | `api/realtime/`（WS hub、LINE outbox、SLA 等 worker）|
| api | API schema | `api/models/generated.py`（由 openapi.yaml 生成）|
| web | gate 層 | `web/src/components/layout/AuthGuard.tsx` · `web/src/lib/{appMode,rolePolicy}.ts` |
| web | 消費層 | `web/src/lib/{api,cache,realtime,sse}.ts` · `web/types/api.generated.ts` |
| knowledge-refinery | Medallion pipeline | `data/pipeline/{raw_to_bronze,bronze_to_silver}/` · `data/llms/` · `data/storage/{raw,bronze,silver}/` |
| knowledge-refinery | 精煉服務 / 審核 UI / Publisher | 獨立服務 codebase [待確認：P4 結構指南待建] |
| technician-platform | OHS API / 事件層 / 投影 | 獨立服務 codebase [待確認：P4 結構指南待建] |

深度參考：各系統完整設計見 [../agent/P1/05_architecture_and_design.md](../agent/P1/05_architecture_and_design.md)、[../api/P1/05_architecture_and_design.md](../api/P1/05_architecture_and_design.md)、[../technician-platform/P1/05_architecture_and_design.md](../technician-platform/P1/05_architecture_and_design.md)、[../web/P1/05_architecture_and_design.md](../web/P1/05_architecture_and_design.md)、[../knowledge-refinery/P1/05_architecture_and_design.md](../knowledge-refinery/P1/05_architecture_and_design.md)、[../00_platform/P1/07_workorder_platform_design.md](../00_platform/P1/07_workorder_platform_design.md)。

---

*文件結尾 — 15_SDS 軟體詳細設計書 v1.0 / 2026-07-07*
