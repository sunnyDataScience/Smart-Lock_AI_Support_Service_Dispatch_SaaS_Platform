---
title: 產品策略（Product Strategy）
version: 1.0
status: active
owner: 平台產品負責人
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P1/06_platformization_strategy.md
  - smartlock-docs/00_platform/P1/05_platform_architecture_L1.md
  - smartlock-docs/00_platform/P1/07_workorder_platform_design.md
  - smartlock-docs/README.md
  - smartlock-docs/00_platform/P2/04_adr/（ADR-P001~P014）
---

# 00 產品策略 — Smart Lock AI 客服 + 派工 SaaS 平台

> **一句話**：本平台是「**藍領營運的商業邏輯編譯器**」——以智慧鎖產業為首個垂直，提供 LINE AI 客服 + 派工 + 報價 + 帳務的一體化 SaaS，並以可組合的積木本體論與 AI Onboarding Compiler，一產業一產業複製到整個藍領服務業。

---

## 1. 產品願景（Vision）

**把藍領服務業的營運邏輯，從老師傅的腦袋與紙本，編譯成平台上可執行、可累積、可複製的商業邏輯資產。**

藍領服務業（鎖匠、水電、空調、家電維修……）的共同結構是「**客服接單 → 診斷 → 派工 → 到府施工 → 報價收款 → 對帳結算**」。這條鏈今天散落在 LINE 對話、電話、紙本簽單與 Excel 之間；每一家品牌都在重複發明同一套營運流程，且流程只存在於資深員工的默會知識（tacit knowledge）裡。

本平台的長期願景：

1. **每一個藍領垂直的營運流程**，都能被表達為平台上宣告式的 flow 定義（工單狀態機 + 金流步驟 + 領域積木）。
2. **每一個垂直的診斷知識**，都能被精煉成 AI 客服可用的知識庫（事實語料）與行為規範（skill）。
3. **累積的積木庫與 flow 定義本身成為護城河**——越晚進場的競爭者，越無法複製這套逐產業沉澱下來的商業邏輯本體論。

定位語出處與完整推導見 [`../00_platform/P1/06_platformization_strategy.md`](../00_platform/P1/06_platformization_strategy.md) §9。

---

## 2. 問題陳述

### 2.1 藍領服務業的結構性痛點（以智慧鎖為首個垂直）

| 痛點 | 具體樣貌（智慧鎖售後場景）|
|---|---|
| **知識鎖在人身上** | 客服全靠老師傅；新客服要訓練約 3 個月才能上手；老師傅離職，know-how 一起離開 |
| **溝通通道原始** | 消費者從 LINE 湧入，人工逐條詢問品牌、型號、地址，再紙本記錄 |
| **派工靠人腦排** | 派錯師傅、排錯時段直接產生賠付與客訴 |
| **帳務黑箱** | 師傅、品牌、平台三方以 Excel 對帳，月結週期長、爭議多 |
| **急件無標準處理** | 被鎖門外、門內受困等急件需要即時判斷與強制轉真人，人工難以穩定執行 |

### 2.2 為什麼通用工具解決不了

n8n / Zapier 等通用工作流工具，以及各家 no-code 平台，**沒有藍領原生語義**：到府、實體簽名、施工照存證、保固判定、技師跨品牌媒合、LINE 客服閉環——這些概念在通用工具裡不存在，得由每個客戶自己用低階節點拼裝，拼出來又淺又脆。ServiceTitan 證明了「垂直深耕的派工 SaaS」是十億美元級生意，但它深綁北美 HVAC／水電生態，不覆蓋亞洲市場、LINE 通訊生態與 AI 診斷場景。

### 2.3 商業結構前提

本平台的商業結構有三個特徵（詳見 [`../00_platform/P1/05_platform_architecture_L1.md`](../00_platform/P1/05_platform_architecture_L1.md) §2）：

1. **per-brand bundle 可獨立部署**：每個加盟品牌一套物理隔離、可完整獨立部署的單體（web／api／agent／品牌庫／Redis／MCP-RAG），資料主權清楚（ADR-P005）。
2. **集中共用平台**：Casdoor（身分／租戶／License）、SigNoz（可觀測性）、technician-platform（技師共享池）、Kafka（事件骨幹）、平台維運 console 由平台方集中營運。
3. **License 附加系統**：knowledge-refinery（知識精煉）等模組為 License 開通的附加品項；「開通哪些模組」由 License 決定。

---

## 3. 北極星（North Star）— 流程自動化護城河：三層複利

本平台的北極星不是單一功能指標，而是**三層互相餵養的複利結構**（出處：`06_platformization_strategy.md` §9，ADR-P011）：

1. **積木飛輪**：每落地一個產業 → 學到新積木 → 進入版本化積木庫（Block Ontology）；越後面的產業越是既有積木重組，onboarding 越快。
2. **AI Onboarding Compiler**：AI 把客戶的 tacit 流程（SOP 文件／訪談／舊系統匯出）**編譯成 flow DSL**，匯入即在 UI 呈現，人審後上線。
3. **Flow ＝ 商業邏輯本體論**：累積的 flow 定義 + 積木庫**編碼各產業的營運邏輯**，形成資料／本體論護城河與客戶轉換成本。

**三條實作鐵律**（策略層承諾，違反即偏航）：

- **DSL-first**：先定 flow DSL + 積木契約 + 執行引擎（能手寫、能執行、能驗證），AI 匯入與拖拉 UI 是疊上去的薄層。順序做反 = AI 產出引擎跑不動的東西。
- **飛輪 bootstrap**：頭 2–3 個產業的積木**手工建**；積木庫夠大，AI 編譯命中率才起飛——誠實面對冷啟動，不對外過早承諾「AI 一鍵匯入」。
- **安全 HITL**：凡涉及金流／派工／同意書的流程，AI 編譯產出**必過人工審核**才上線，不盲匯入。

---

## 4. 產品定位與一句話

**Smart Lock AI Support & Service Dispatch SaaS Platform**：LINE Bot 智慧鎖 AI 客服 + 派工營運 SaaS——先把智慧鎖垂直做深，再以平台化架構跨藍領產業複製。

平台由 **6 個系統**構成（詳見 [`../README.md`](../README.md)）：

| 系統 | 角色 |
|---|---|
| **agent** | LINE Bot AI 客服（LockCore 核心引擎，Skill 行為驅動 + RAG 檢索）|
| **api** | FastAPI 派工營運控制平面（工單／派工／報價／帳務／結算）|
| **web** | Next.js 多站前端（品牌營運後台、平台 console、landing）|
| **knowledge-refinery** | 知識精煉服務 + 審核 UI（License 附加系統，ADR-P001）|
| **technician-platform** | 技師共享池獨立系統（跨租戶技師身分 + 師傅 web，ADR-P004）|
| **00_platform（整合層）** | Casdoor／SigNoz／Kafka／平台維運 console 等集中共用基礎設施 |

---

## 5. 差異化與護城河

**差異化公式 = 藍領原生積木本體論 × AI Onboarding Compiler × 累積商業邏輯。**

| 對照對象 | 它有什麼 | 它缺什麼（我們的差異）|
|---|---|---|
| **n8n / Zapier** | 通用工作流編輯器 | 無藍領原生語義（到府、簽名、施工照、保固、技師媒合、LINE 閉環）；只有編輯器，無累積的商業邏輯本體論 |
| **ServiceTitan** | 垂直派工 SaaS 標竿 | 深綁北美 HVAC／水電生態；無亞洲 LINE 場景、無 AI 診斷客服、無跨產業積木飛輪 |
| **自建系統** | 貼合單一品牌 | 每家重複造輪子；知識不沉澱、不可複製、離職即流失 |

三個難以複製的結構：

1. **藍領原生積木庫**：派工、技師媒合、到府同意書、施工照／簽名存證、保固判定、LINE 溝通、報價核准、對帳結算——每個積木本身就垂直很深（`06` §4.4、§6.4）。
2. **AI Onboarding Compiler**（ADR-P011，🔜 規劃中，Roadmap 見 §9）：把客戶 SOP 編譯成 draft flow DSL 的能力，建立在積木本體論之上——沒有積木庫，AI 編譯無詞彙可對映。
3. **孿生對稱**：AI 流程編譯器與 knowledge-refinery 是同一個 HITL 模式（draft → 人審 → commit）的兩個化身——**一煉知識、一煉流程**，共用審核 UI 骨架與 License 附加定位（ADR-P011／ADR-P001）。競爭者要複製，得同時複製兩條精煉管線與其治理。

---

## 6. 平台化策略 — TRIZ 矛盾解析

平台化的核心矛盾：**「快速跨產業重用」與「垂直領域整合深度」看似互斥**。本平台以 TRIZ 方法論正面化解（完整推導見 `06_platformization_strategy.md` §4）。

### 6.1 矛盾形式化

- **技術矛盾（TC）**：提升系統通用性／可重用性（跨產業共用一套核心），則惡化垂直領域整合深度（貼合變淺、複雜度上升）。
- **物理矛盾（PC）**：平台**必須同時是通用的**（才能重用）**又是專用的**（才能把藍領垂直做深）。

### 6.2 以 TRIZ 分離原則化解 PC（引自 `06` §4.2）

| 分離原則 | 套用到本平台 |
|---|---|
| **按系統層級分離**（最關鍵）| **核心層通用、配置層專用**：把不變的平台原語（工單引擎、agent runtime、金流軌、身分/RBAC、事件骨幹）做通用；把變動的領域邏輯（診斷知識、model 編排、工單/金流 flow）做成**配置/組合**。通用性在核心層、專用性在配置層——**不在同一層競爭**。 |
| **空間分離** | 分層架構：底層通用核心 + 上層領域配置層，物理分開。 |
| **時間分離** | 平台在**設計/build 時是產業無關**的；**專用化發生在「配置/部署時」**（FDE 配置），而非「fork code 時」。 |
| **條件分離** | 同一引擎依「載入哪套 flow 定義 / skill / 編排配方」而表現為不同產業行為。 |

### 6.3 相關發明原則（引自 `06` §4.3）

- **#1 分割**：工單/金流拆成可組合積木。
- **#2 抽出**：把「隨產業變」的部分（知識/flow/model 配方）抽離出固定核心。
- **#3 局部品質**：**垂直深度活在積木裡**——每個積木為其專用功能最佳化。
- **#40 複合**：平台 = 固定核心 + 可插拔領域模組。
- **#15 動態化／#35 參數改變**：flow/積木以配置驅動，改行為不改碼。
- **#25 自服務／#24 中介**：FDE/客戶經 UI 自行組裝（拖拉）；一層**宣告式 flow DSL** 作為 UI 與引擎的中介。
- **#10 預先作用／#26 複製**：每產業一套**範本**（藍領服務範本 → 複製 → 微調）。

### 6.4 化解結論

> **抽象化「不必然」犧牲垂直整合——前提是把垂直深度從「fork 的 code」搬到「可組合的領域配置（積木＋知識＋flow DSL）」。**（`06` §4.4）

「深度」被重定位：不再是「核心寫死多深」，而是「用多深的領域積木組多細的 flow」。犧牲整合性的風險只在**積木太通用太淺**時發生，緩解 = **深度領域積木 + 逃生艙**（plugin SDK + webhook 外呼，拒絕 inline code 節點；裁定見 `07_workorder_platform_design.md` §9 決策 C）。

### 6.5 兩層職責邊界（FDE 邊界，ADR-P009）

**可重用平台核心（FDE 永不動）**（引自 `06` §5.1）：

| 能力 | 元件 |
|---|---|
| 身分 / RBAC / 租戶 / License | Casdoor（ADR-P003／ADR-P006）|
| 工單引擎（狀態機執行器）| api 工單核心（把 flow 當**資料**解釋執行）|
| 客服 agent runtime | LockCore |
| 金流 / 對帳 / 結算軌 | api 金流核心 |
| 事件 / 即時骨幹 | Kafka / Redis（ADR-P007）|
| 可觀測性 | SigNoz + OPIK（ADR-P002）|
| 技師共享池 | technician-platform（ADR-P004）|
| 多租戶 provisioning | per-brand bundle（ADR-P005）|

**領域配置層（FDE 每個新產業只做 4 配置面）**（引自 `06` §5.2 + §8.2）：

| FDE 工作 | 內容 | 對應核心 |
|---|---|---|
| **① 診斷系統** | 客服知識核心 + model 編排配方 + api 調用效率 | agent runtime + Model Orchestration Layer（ADR-P008）|
| **② 知識庫精煉** | 該產業的事實語料 + skill 行為 | knowledge-refinery（ADR-P001）+ RAG-via-MCP（ADR-004）|
| **③ 工單 / 金流 flow** | 該產業的工單生命週期 + 金流步驟（積木組裝，DSL）| 工單引擎 + flow DSL（ADR-P010）|
| **④ 後台 UI 組裝** | 共用元件庫組裝畫面 + 自訂 panel（逃生艙）| `DynamicForm`/`DynamicTable` + `ui_composition` |

> **關鍵**：這 4 面都是**配置／組裝**，不是改核心 code。新產業上線 = 換一套「診斷腦 + 知識 + flow 定義 + UI 組裝」，核心原封不動。

### 6.6 Flow-as-Blocks 分期（ADR-P010）

- **Phase 1**：工單引擎**配置驅動**（DSL 解釋的狀態機）——FDE 先手寫／改 DSL。**真正的槓桿在引擎，不在 UI。**
- **Phase 2**：在穩定 DSL 上疊**拖拉編輯器** + 積木庫 + 範本（🔜 規劃中）。
- ⚠️ 策略紀律：絕不先做華麗拖拉 UI 而引擎未抽象化——UI 會產不出引擎能執行的東西。

---

## 7. 商業模式

**License 開通 + per-brand bundle + 附加模組選配**（ADR-P003／ADR-P005；詞彙定義見 `05_platform_architecture_L1.md` §7）。

### 7.1 變現結構

| 層 | 內容 | 計價單位 |
|---|---|---|
| **基礎 License** | per-brand bundle 一套（web 品牌營運後台 + api + agent + 品牌庫 + Redis + MCP-RAG）+ 綁定品牌自己的 LINE channel | 每品牌授權（金額 [待確認]）|
| **附加模組** | knowledge-refinery（知識精煉 + 審核 web）、Agent Configuration Studio（品牌自服務調校，ADR-P013）、AI Onboarding Compiler（🔜 規劃中，ADR-P011）| License 選配（金額 [待確認]）|
| **集中共用服務** | 技師共享池媒合（technician-platform）、平台治理 | 內含於平台營運（分潤機制 [待確認]）|

### 7.2 開通機制

1. 潛在加盟品牌經 landing 申請 → **Casdoor subscription 作為 License 開通閘門**（ADR-P003）。
2. License 開通 → provisioning：部署 per-brand bundle → 建品牌庫 → **綁定該品牌 LINE channel 與設定** → 健康檢查（ADR-P005；provisioning 自動化屬 Roadmap Phase 3，🔜 規劃中）。
3. 「開通哪些附加模組」由 License 決定——整體架構圍繞此微調。

### 7.3 結構優勢

- **物理隔離 = 資料主權可售**：一品牌一庫、一 bundle，品牌資料與 LINE channel 完全隔離，是對加盟品牌的關鍵承諾。
- **附加模組 = 擴充營收**：知識精煉、Agent Studio、AI 編譯器都是同一 HITL 骨架的變體，邊際成本遞減。
- **技師共享池 = 網路效應**：技師是跨品牌身分（ADR-P004），品牌越多技師越有價值，技師越多品牌派工越快。

---

## 8. 目標客群輪廓（策略層）

依 `05_platform_architecture_L1.md` §2 外部角色與 ADR-P006 四方 RBAC：

| 客群 | 身分 | 對平台的價值 / 期望 |
|---|---|---|
| **加盟品牌（租戶）** | 智慧鎖品牌商，購買 License | 快速獲得完整售後營運系統（AI 客服 + 派工 + 帳務），不用自建；資料主權物理隔離；租戶 Admin 可自助開帳（ADR-P006）|
| **品牌派工小編** | 品牌自己的營運人員 | 用品牌營運後台監看 AI 對話、處理 escalation、派工與對帳 |
| **簽約師傅／鎖匠** | 跨租戶技師身分（technician-platform 管理）| 註冊、上線、接單、回報施工、月結透明 |
| **終端消費者** | LINE 用戶（智慧鎖屋主）| 在 LINE 上報修，AI 即時診斷自助解決；急件（被鎖門外／門內受困等）強制轉真人 |
| **平台維運方（Super Admin）** | 我方 | 跨租戶治理、License 管理、平台可觀測性 |
| **FDE（Forward Deployed Engineer）** | 我方領域配置工程師 | 每個新產業只動 4 配置面（§6.5），不改核心 |
| **潛在加盟品牌** | 尚未簽約的品牌 | 經 landing 了解平台 → 申請 License 開通 |

---

## 9. 成功指標與里程碑

### 9.1 策略層 KPI

> 指標**類別**源自產品營運目標；凡具體數值未由平台級文件證實者標 [待確認]。

| 類別 | 指標 | 目標 |
|---|---|---|
| 客服品質 | AI 客服準確率（標準題集 UAT）| ≥ 80%，數值屬品牌合約層 [待確認] |
| 客服品質 | 消費者自助解決率 | ≥ 60%（上線後觀測期）[待確認] |
| 營運效率 | 新產業 onboarding 週期（FDE 4 配置面完成時間）| 逐產業遞減（積木飛輪的直接量測）[待確認] |
| 飛輪健康 | AI 編譯命中率（客戶流程步驟被既有積木覆蓋比例）| 逐產業上升（🔜 AI Compiler 上線後量測）|
| 工程體質 | DORA：Lead time < 1 天／CFR < 15%／MTTR < 1 天 | [待確認]（沿用工程基線目標）|
| 可用性 | 系統 Uptime | ≥ 95% 合約基線、≥ 99.5% 營運目標 [待確認] |

### 9.2 平台演進里程碑（對映 `05_platform_architecture_L1.md` §6）

| 階段 | 內容 | 狀態 |
|---|---|---|
| **Phase 1 — 正確性與絲滑即時** | RBAC 全面 enforce（ADR-P006）、Redis 即時骨幹上線（ADR-P007）、SigNoz + OPIK 可觀測性接線（ADR-P002）、知識精煉落點對齊（ADR-P001）| 進行中 |
| **Phase 2 — 身分／知識／技師平台** | Casdoor 導入（ADR-P003）、RAG-via-MCP 語義檢索層（ADR-004）、technician-platform 獨立系統（ADR-P004）、讀寫分離 | 🔜 規劃中 |
| **Phase 3 — 事件骨幹與治理健壯化** | Kafka 事件骨幹（ADR-P007）、per-brand provisioning 自動化 + CD（ADR-P005／ADR-P012）| 🔜 規劃中 |
| **工單平台化** | flow DSL + 引擎 → 通用工單核心 → locksmith Vertical Pack → 第 2 產業驗證 → FlowEditor + AI Compiler（`07_workorder_platform_design.md` §8 五階段）| 🔜 規劃中 |

---

## 10. 策略風險與緩解

| # | 風險 | 嚴重度 | 緩解 |
|---|---|---|---|
| SR-1 | **積木太通用太淺**，失去垂直深度，退化成又一個 n8n | 🔴 高 | 深度藍領積木庫（積木本身垂直很深）+ 逃生艙（plugin SDK / webhook，`07` §9 決策 C）|
| SR-2 | **先做 UI、引擎未抽象化**——拖拉編輯器產不出引擎能執行的 flow | 🔴 高 | DSL-first 鐵律（§3）：引擎 → DSL 穩定 → 才疊 UI 與 AI 編譯 |
| SR-3 | **飛輪冷啟動**：頭 2–3 產業積木庫小、AI 編譯命中率低 | 🟡 中 | 誠實面對：頭 2–3 產業積木手工建；不以「AI 一鍵匯入」過早對外承諾 |
| SR-4 | **AI 編出錯誤／不安全流程**（金流、派工、同意書）| 🔴 高 | HITL 硬 gate：draft → 人審 → 上線；匯入靜態驗證（積木契約，ADR-P011）|
| SR-5 | **LLM 供應商鎖定** | 🟢 已結構性緩解 | Model Orchestration Layer：供應商 = 配置（model 字串 + credential），換家零改碼（ADR-P008）|
| SR-6 | **資料只是 log、不沉澱成資產** | 🟡 中 | 知識飛輪：knowledge-refinery 把診斷素材精煉為事實語料（pgvector）+ 行為 skill（ADR-P001）；flow 定義本身即商業邏輯資產 |
| SR-7 | **Casdoor 成關鍵單點** | 🟡 中 | HA + 備份（ADR-P003）；License 語義超出內建能力時外掛 license 服務 |
| SR-8 | **per-brand 部署運維擴散** | 🟡 中 | provisioning 自動化 + 升級策略（Roadmap Phase 3）；品牌數成長至不可持續時重新評估共用控制面（ADR-P005 重評觸發）|
| SR-9 | **長尾流程 no-code 覆蓋不全** | 🟡 中 | 逃生艙雙軌：緊耦合自訂邏輯走 plugin SDK（過審 + 版本化）、鬆耦合走 webhook 外呼；拒絕 inline code（`07` §9）|

---

## 附：相關文件

- 市場需求細節 → [`./01_MRD.md`](./01_MRD.md)
- 平台架構總覽 → [`../00_platform/P1/05_platform_architecture_L1.md`](../00_platform/P1/05_platform_architecture_L1.md)
- 平台化策略完整推導 → [`../00_platform/P1/06_platformization_strategy.md`](../00_platform/P1/06_platformization_strategy.md)
- 通用工單平台詳細設計 → [`../00_platform/P1/07_workorder_platform_design.md`](../00_platform/P1/07_workorder_platform_design.md)
- 平台級架構決策 → [`../00_platform/P2/04_adr/`](../00_platform/P2/04_adr/)（ADR-P001~P014）

*— 00_Product_Strategy v1.0 / 2026-07-07*
