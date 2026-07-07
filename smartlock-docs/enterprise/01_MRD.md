---
title: 市場需求文件（MRD）
version: 1.0
status: active
owner: 產品經理
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P1/06_platformization_strategy.md
  - smartlock-docs/00_platform/P1/05_platform_architecture_L1.md
  - smartlock-docs/00_platform/P1/07_workorder_platform_design.md
  - smartlock-docs/README.md
  - smartlock-docs/00_platform/P2/04_adr/（ADR-P003/P004/P005/P006/P011）
---

# 01 市場需求文件（MRD）— Smart Lock AI 客服 + 派工 SaaS 平台

> **讀者**：產品經理、市場／BD、FDE、客戶成功。
> **回答**：市場長什麼樣、客群怎麼分、誰買單為何買、競品是誰、我們如何一產業一產業擴張。
> 策略層願景與商業模式見 [`./00_Product_Strategy.md`](./00_Product_Strategy.md)。

---

## 1. 市場概述

**目標市場：亞洲藍領服務業的營運數位化，以智慧鎖售後服務為首個灘頭（beachhead）。**

藍領服務業（鎖匠、水電、空調、家電維修、清潔、搬家……）共享同一條營運鏈：**客服接單 → 診斷 → 派工 → 到府施工 → 報價收款 → 對帳結算**。這條鏈在亞洲市場有兩個結構性特徵：

1. **LINE 是事實上的客服入口**——消費者不裝 App、不打 0800，直接在品牌 LINE 官方帳號報修。
2. **營運知識鎖在資深師傅腦中**——診斷、報價、派工判斷全是默會知識，沒有系統化沉澱。

智慧鎖是理想的首個垂直：產品單價高（售後有付費意願）、故障場景急迫（被鎖門外、門內受困）、診斷知識高度結構化（品牌 × 型號 × 故障碼）、且服務閉環天然落在 LINE 上。

市場規模（TAM／SAM／SOM）：[待確認]——尚無平台級文件載明量化估算，需市場團隊補充調研。

---

## 2. 市場問題與機會

### 2.1 需求端的痛（品牌商視角）

| 痛點 | 代價 |
|---|---|
| 客服全靠老師傅，新客服訓練期約 3 個月 | 人力成本高、擴張受限、離職即知識流失 |
| LINE 訊息人工逐條問品牌／型號／地址 | 回應慢、錯漏多、消費者體驗差 |
| 派工靠人腦，派錯就賠 | 直接賠付 + 客訴 + 師傅抱怨 |
| 三方（品牌／師傅／平台）Excel 對帳 | 月結週期長、每月吵帳 |
| 急件（被鎖門外／門內受困）無標準流程 | 安全風險與商譽風險 |

### 2.2 供給端的缺口（工具市場視角）

- **通用工作流工具（n8n／Zapier）沒有藍領原生語義**：到府、實體簽名、施工照存證、保固判定、技師跨品牌媒合、LINE 客服閉環，在通用工具中都不存在，客戶得自己用低階節點拼——拼出來太通用太淺，撐不起垂直營運（`06_platformization_strategy.md` §4.4、§6.4）。
- **垂直 SaaS 標竿（ServiceTitan）不覆蓋亞洲**：綁定北美 HVAC／水電生態，無 LINE、無中文 AI 診斷。
- **自建**：每家品牌重複造輪子，造出來的系統不含 AI 診斷與知識精煉能力。

### 2.3 機會

**「ServiceTitan 級快速建置 × 藍領垂直深度 × 亞洲 LINE + AI 診斷」的空白帶。** 平台以智慧鎖切入建立完整營運閉環，再以 Vertical Pack 機制（§8）低邊際成本複製到其他藍領垂直。

---

## 3. 目標客群分群（Segmentation）

依平台四方 RBAC 模型（ADR-P006）與外部角色圖（`05_platform_architecture_L1.md` §2）：

| 分群 | 定義 | 與平台的關係 | 帳號來源 |
|---|---|---|---|
| **加盟品牌（租戶）** | 智慧鎖品牌商；付費主體 | 購買 License → 獲得一套物理隔離的 per-brand bundle + 綁自己的 LINE channel（ADR-P005）| Casdoor org；租戶 Admin 自助開帳 |
| **品牌派工小編** | 品牌自己的營運人員 | 日常使用品牌營運後台（派工／工單／客服監看）| 租戶 Admin 開通 |
| **技師（簽約師傅／鎖匠）** | 現場施工者；**跨租戶身分** | 經 technician-platform 註冊／上線／接單／月結（ADR-P004）| Casdoor + 技師平台 |
| **終端消費者** | 智慧鎖屋主（LINE 用戶）| 不付費給平台；在品牌 LINE 官方帳號報修，由 AI 客服服務 | LINE 身分，免註冊 |
| **平台維運方（Super Admin）** | 我方 | 跨租戶治理、License 管理 | 平台建立 |
| **潛在加盟品牌** | 尚未簽約的品牌商 | 經 landing 申請 → Casdoor License 開通 | — |

> 分群關鍵洞察：**付費者（品牌）、使用者（小編／消費者）、供給者（技師）是三種不同人**。產品必須同時讓品牌覺得值（省人力＋資料主權）、讓小編好用（後台）、讓技師願意留在池子裡（接單透明＋月結準時）。

---

## 4. 使用者 Persona 與採購動機

### 4.1 進入點對照（引自 `README.md`）

| 角色 | 進入系統 | 協議 |
|---|---|---|
| 智慧鎖終端客戶（消費者）| **agent**（LINE 官方帳號）| LINE webhook |
| 品牌營運人員 | **web** dispatch portal :3000 → api dispatch :8001 | HTTPS / WebSocket |
| 簽約師傅 | technician-platform 師傅 web（註冊／上線／工作台）| HTTPS / WebSocket |
| 平台管理員 | **web** platform portal :3003 → api platform :8003 | HTTPS |
| 潛在加盟品牌 | **web** landing :3002 → api platform :8003（品牌申請）| HTTPS |

### 4.2 Persona 與動機

**P1 品牌決策者（採購者）**
- 痛：售後客服人力貴、對帳亂、know-how 留不住；想上系統但不願資料進共用池。
- 買單理由：License 開通即得完整營運系統（AI 客服 + 派工 + 報價 + 帳務）；**per-brand bundle 物理隔離**（一品牌一庫、綁自己的 LINE），資料主權清楚；附加模組（知識精煉、Agent Studio）按需選配。
- 決策關鍵問句：「我的客戶資料放哪？」「AI 亂承諾誰負責？」→ 答案分別是「你自己的隔離 bundle」與「HITL + 行為規範 + 人工接管」。

**P2 品牌派工小編（日常使用者）**
- 痛：LINE 訊息接不完、急件怕漏、派工排程靠記憶。
- 期望：AI 先接大多數對話，異常才進來；escalation 有明確佇列；派工看板即時。

**P3 簽約師傅（供給端）**
- 痛：單源不穩、回報靠拍照傳 LINE 群、月結不透明。
- 期望：跨品牌接單（技師共享池讓單源變多）、施工回報結構化、結算清楚。

**P4 終端消費者（量大、個體影響小）**
- 場景：LINE 報修 → AI 對話診斷 → 自助解決，或轉派工 → 確認結案。
- 關鍵時刻：急件（被鎖門外／門內受困／安全風險／怒客）必須即刻升級真人——這是信任的底線。

**P5 FDE（我方，擴張引擎）**
- 每個新產業只做 4 配置面：診斷系統、知識精煉、flow DSL、UI 組裝（`06` §8.2）——採購後的 onboarding 由 FDE 完成，品牌無需技術團隊。

### 4.3 採購旅程

潛在品牌（landing 申請）→ 平台方商務洽談 → **Casdoor License 開通**（ADR-P003）→ provisioning（部署 bundle＋建庫＋綁 LINE）→ FDE 配置（智慧鎖 pack 為預設）→ 小編培訓上線 → 附加模組追加銷售（refinery／Agent Studio）。

---

## 5. 競品分析

### 5.1 範式對照（可行性基準，引自 `06` §6.1）

| 面向 | 判定 | 依據 |
|---|---|---|
| flow 編排做成宣告式狀態機/節點圖 | **高可行** | 成熟範式：BPMN/Camunda、Temporal、n8n、ServiceTitan workflow、OpenAI Assistants/AgentBuilder、Retool workflow 皆已驗證 |
| 前端拖拉 = 薄編輯器產出 DSL | **高可行** | 編輯器只是產生/編修 flow 定義，不含執行邏輯 |
| 全 no-code 覆蓋所有垂直細節 | **中** | 長尾需逃生艙（自訂節點），否則會退回「太通用太淺」的陷阱 |

### 5.2 競品定位

| 競品 | 類型 | 強項 | 本平台相對定位 |
|---|---|---|---|
| **ServiceTitan** | 垂直派工 SaaS | 北美 HVAC／水電生態完整、workflow 成熟 | 我們針對**亞洲藍領 + LINE + AI 診斷**；且以積木本體論跨垂直，非鎖死單一產業生態 |
| **n8n / Zapier** | 通用工作流工具 | 節點生態大、上手快 | 它們**只有編輯器**；我們有藍領原生積木語義 + AI Onboarding Compiler + 累積商業邏輯本體論（`06` §9）|
| **BPMN / Camunda(Zeebe)** | 流程標準／引擎 | 標準化、有現成編輯器 | 語義通用、藍領弱、AI 生成難；本平台 DSL 自建（藍領語義 + AI 可生成 + 可驗證，`07` §9 決策 A）|
| **Temporal** | durable 執行引擎 | 重試／saga 成熟 | 定位為**可替換執行後端**而非競品：DSL 與 executor 解耦，未來長流程可換 Temporal、DSL 不動 |
| **Retool 類** | 內部工具建置 | 後台快速拼裝 | 無工單領域模型、無派工／金流軌、無 AI 客服閉環 |
| **品牌自建** | in-house | 貼合單一品牌 | 無知識精煉、無技師共享池網路效應、成本由單一品牌獨扛 |

### 5.3 競爭壁壘總結

競爭者要追上，需同時具備：藍領原生積木庫（逐產業手工沉澱）＋ AI 編譯器（依賴積木詞彙）＋ 雙精煉管線（知識＋流程，同一 HITL 骨架）＋ 技師共享池網路效應。單點模仿（例如只做拖拉編輯器）無法複製整體。

---

## 6. 差異化價值主張（MRD 版）

> **「ServiceTitan 級快速建置 × 藍領垂直深度 × 亞洲 LINE + AI 診斷落地。」**（`06` §6.4）

對三類買家各說一句話：

- **對品牌**：一紙 License，30 天內擁有自己品牌的 AI 客服 + 派工 + 帳務系統，資料物理隔離（上線週期數字 [待確認]）。
- **對技師**：一個身分，跨品牌接單，回報與月結全程透明。
- **對平台自己（跨產業複製）**：新產業不改核心 code，FDE 4 配置面 + Vertical Pack 即上線。

---

## 7. 市場需求清單（Market Requirements）

### 7.1 平台級四大需求（引自 `06` §2 需求拆解表）

| # | 需求 | 本質 |
|---|---|---|
| A | 模型調用解耦、不依賴任何供應商 | 供應商無關的**模型編排層** |
| B | 新產業（同需工單+客服）可重用 → 抽象化；但不能犧牲垂直整合 | **通用 vs 專用的矛盾**（TRIZ 解）|
| C | 新產業時 FDE 只需做：診斷系統(知識核心+model 編排+api 調用效率)、知識庫精煉、工單/金流 flow | **FDE 職責邊界 = 領域配置層** |
| D | 工單/金流做成積木、前端拖拉串工作流（參 ServiceTitan / 早期 OpenAI agent builder，但針對藍領）| **flow 宣告式編排 + 積木庫** |

拆解為市場需求條目：

| MR | 需求陳述 | 對應能力 | 狀態 |
|---|---|---|---|
| MR-01 | 品牌採購後不被任何 LLM 供應商綁架，模型可換、成本可控 | Model Orchestration Layer（ADR-P008）| 設計定案 |
| MR-02 | 平台能以同一套核心服務多個藍領產業，且各產業整合深度不打折 | 核心/配置分層（ADR-P009）+ 深度積木 + 逃生艙 | 設計定案 |
| MR-03 | 新產業 onboarding 由 FDE 以配置完成，無需改核心程式 | FDE 4 配置面（`06` §8.2）| 設計定案 |
| MR-04 | 品牌／FDE 能以積木組裝工單與金流流程，最終走向拖拉編排 | Flow-as-Blocks DSL（ADR-P010）| 🔜 規劃中（DSL-first 分期）|
| MR-05 | 客戶既有 SOP 能被 AI 編譯成可執行流程草稿，人審後上線 | AI Onboarding Compiler（ADR-P011）| 🔜 規劃中 |

### 7.2 智慧鎖首垂直的功能需求範圍（業務層）

| MR | 需求陳述 | 承載系統 |
|---|---|---|
| MR-10 | 消費者在品牌 LINE 官方帳號報修，AI 依品牌×型號×症狀診斷並引導自助解決 | agent（LockCore + Skill + RAG）|
| MR-11 | 急件（被鎖門外／門內受困／安全風險／怒客）強制即時轉真人 | agent → api escalation |
| MR-12 | AI 不得越權承諾（final quote／折扣／免費保固自動攔截）| agent 行為規範 + 程式判定 |
| MR-13 | 派工：工單建立 → 技師媒合 → 指派 → 到場 → 施工回報（照片／簽名存證）→ 結案 | api + technician-platform |
| MR-14 | 報價與核准：報價單 → 客戶核准 → 施工 → 收款 | api 工單/金流軌 |
| MR-15 | 帳務與結算：三方（品牌／師傅／平台）月結對帳自動化 | api 結算軌 |
| MR-16 | 品牌知識持續精煉：診斷素材 → 事實語料（pgvector）+ 行為 skill，人審後生效 | knowledge-refinery（License 附加）|
| MR-17 | 品牌自服務調校 AI 客服（skill／檢索權限／prompt，分層保護）| Agent Configuration Studio（ADR-P013）|

---

## 8. 平台化擴張策略 — Vertical Pack 產業包

擴張的機制單位是 **Vertical Pack**：一個產業的全部領域配置打成一包、版本化發行（`07_workorder_platform_design.md` §4）。

### 8.1 Pack 結構（Manifest）

```yaml
pack: locksmith
version: 1.2.0
extends: blue-collar-service@2.x     # 可繼承藍領基底 pack（共用預設）
field_metadata: [ {entity: work_order, key: brand, type: enum, options: [...], required: true}, ... ]
flow: ./flow.dsl.json                # 工單+金流狀態機
catalog:  { services: [...], materials: [...], pricing_rules: [...] }
knowledge: { skills: [locksmith-cs-sop, locksmith-product-knowledge], rag_corpus: pgvector://locksmith }
ui_composition: { screens: [ {route: /work-orders, layout: [...component refs...]} ] }
blocks: [ dispatch, quote_approval, onsite_consent, collect_payment, settle, ... ]
```

- **品牌（租戶）= 裝一個 pack@version + 租戶級覆寫**（價目／SLA／品牌參數）。
- `blue-collar-service` 基底 pack 提供藍領共用預設，各垂直 `extends` 之——減少重複、餵飽積木飛輪。

### 8.2 三大地基（引自 `06` §8.1）

| 決策 | 選定 | 說明 |
|---|---|---|
| 工單領域模型 | 通用核心欄 + JSONB 屬性 + `field_metadata` | 可查詢核心 + 產業彈性欄；欄位語義由 metadata 驅動表單/清單/驗證 |
| 後台呈現 | 共用元件庫 + 每產業組裝（**分兩層**）| **欄位層**配置驅動（`DynamicForm`/`DynamicTable` 吃 metadata）、**畫面層**元件組裝（+ 自訂 panel 逃生艙）|
| 產業配置 | **Vertical Pack 產業包** | 一包 = `field_metadata` + `flow DSL` + `catalog` + `knowledge` + `ui_composition` + `blocks`，版本化 |

### 8.3 積木飛輪如何轉

1. 落地產業 N → FDE 手組 flow、發現缺的積木 → 新積木進庫（版本化 + 治理，ADR-P011 Block Ontology）。
2. 產業 N+1 的流程有更高比例被既有積木覆蓋 → onboarding 更快、成本更低。
3. 積木庫夠大後，AI Onboarding Compiler 把客戶 SOP 對映到積木詞彙、產出 draft flow → 人審上線（🔜 規劃中）。
4. **量測指標**：AI 編譯命中率（客戶流程步驟被既有積木覆蓋比例）逐產業上升。

---

## 9. 進場順序與 Roadmap

### 9.1 進場原則

- **智慧鎖先做深**：首垂直必須跑通完整閉環（AI 客服 → 派工 → 金流 → 結算），沉澱第一套 locksmith Vertical Pack。
- **飛輪 bootstrap 誠實面對**：頭 2–3 個產業的積木**手工建**，AI 編譯是積木庫成熟後的加速器，不是第一天的賣點（`06` §9 鐵律）。
- **DSL-first**：引擎與 DSL 先穩，拖拉 UI 與 AI 編譯後上（ADR-P010／ADR-P011）。

### 9.2 階段路線

| 階段 | 市場動作 | 平台能力（對映 `05_L1` §6 / `07` §8）|
|---|---|---|
| **現階段** | 智慧鎖垂直深耕：既有品牌閉環營運、打磨 AI 客服品質與派工效率 | Phase 1：RBAC enforce、Redis 即時、可觀測性、知識精煉落點 |
| **下一階段** | 品牌 onboarding 規模化：租戶自助開帳、技師共享池啟動網路效應 | Phase 2（🔜 規劃中）：Casdoor、RAG-via-MCP、technician-platform 獨立、讀寫分離 |
| **擴張準備** | License provisioning 自動化 → 降低單品牌開通成本 | Phase 3（🔜 規劃中）：Kafka 事件骨幹、per-brand provisioning 自動化 + CD |
| **工單平台化** | locksmith 邏輯打包成第一個 Vertical Pack | 🔜 規劃中：flow DSL + 引擎 → 通用工單核心 → locksmith pack v0 |
| **第 2 產業驗證** | 選定次一藍領垂直（候選產業 [待確認]），驗證「免改核心」成立 | 🔜 規劃中：飛輪 bootstrap、量測 onboarding 週期 |
| **AI 編譯加速** | 以「SOP 匯入即成流程草稿」為擴張賣點 | 🔜 規劃中：FlowEditor 拖拉 + AI Onboarding Compiler + HITL |

---

## 10. 市場風險與假設

### 10.1 關鍵假設（需持續驗證）

| # | 假設 | 驗證方式 |
|---|---|---|
| H1 | 品牌願為「資料物理隔離 + 綁自己 LINE」支付 License 溢價 | 首批品牌簽約轉換率 [待確認] |
| H2 | 藍領各垂直的營運鏈相似度足以讓積木重用率逐產業上升 | 第 2 產業 pack 的既有積木覆蓋率 |
| H3 | 技師願意進共享池（跨品牌接單誘因 > 單一品牌綁定）| 技師註冊/留存數 [待確認] |
| H4 | 消費者接受 AI 首應答（自助解決率達標且不損品牌）| 自助解決率與投訴率觀測 [待確認] |

### 10.2 市場風險

| # | 風險 | 嚴重度 | 緩解 |
|---|---|---|---|
| MRisk-1 | no-code 覆蓋不了垂直長尾，客戶感覺「工具太淺」流失 | 🟡 中 | 逃生艙雙軌（plugin SDK + webhook）；FDE 陪跑補積木（`06` §6.1、`07` §9）|
| MRisk-2 | 積木庫冷啟動期，擴張速度不如敘事預期 | 🟡 中 | 對外承諾對齊實況：頭 2–3 產業以 FDE 手工交付為主，AI 編譯內部先行 |
| MRisk-3 | LLM 供應商價格／政策變動衝擊毛利 | 🟢 已結構性緩解 | 供應商 = 配置，隨時換家（ADR-P008）|
| MRisk-4 | 資料不沉澱，被大廠通用 vertical agent 追上 | 🟡 中 | 知識精煉（事實語料 + skill）與 flow 本體論持續沉澱為轉換成本（ADR-P001／P011）|
| MRisk-5 | 大型垂直 SaaS（ServiceTitan 類）進入亞洲 | 🟡 中 | LINE 生態 + 中文診斷語料 + 在地技師池是其短期難以複製的組合 |
| MRisk-6 | 單一大品牌要求深度客製，拖垮平台通用性 | 🟡 中 | 客製一律落在配置層（pack 覆寫 + 自訂 panel + plugin），核心不分叉（ADR-P009）|

---

## 附：相關文件

- 產品策略與商業模式 → [`./00_Product_Strategy.md`](./00_Product_Strategy.md)
- 平台化策略完整推導（TRIZ／護城河）→ [`../00_platform/P1/06_platformization_strategy.md`](../00_platform/P1/06_platformization_strategy.md)
- 通用工單平台 SDS（Vertical Pack／DSL／積木裁定）→ [`../00_platform/P1/07_workorder_platform_design.md`](../00_platform/P1/07_workorder_platform_design.md)
- 平台架構 L1（角色圖／商業結構／詞彙表）→ [`../00_platform/P1/05_platform_architecture_L1.md`](../00_platform/P1/05_platform_architecture_L1.md)

*— 01_MRD v1.0 / 2026-07-07*
