# AI 藍領客服平台企業架構白皮書 v3

---

## 文件控制（Document Control）

| 項目 | 內容 |
| :--- | :--- |
| 文件標題 | AI 藍領客服平台企業架構白皮書（AI Blue-Collar Customer Service Platform Enterprise Architecture White Paper） |
| 版本 | v3.0 — EA 結構重整版（W1） |
| 日期 | 2026-05-12 |
| 前身 | v2 強化版（2026-05-12）— 戰略 + 技術藍圖混合 |
| 適用框架 | TOGAF 9.2 ADM + ISO/IEC/IEEE 42010:2022 + C4 Model + Gartner Pace-Layered |
| 受眾分版 | Executive Brief / Architecture White Paper / Engineering Reference / Compliance Pack |
| 機密等級 | Confidential — Internal Distribution |
| 作者 | Founder / 平台架構組 |
| Reviewer | TBD（CTO / 客戶資安代表 / 法遵代表） |
| Approver | TBD（CEO / Board） |

> **重要說明**：本版（v3）為「W1 結構重整版」。所有現有內容已按 EA 規格重新分類；標 `[TBD-W2]` 的章節為待補缺口（C4 視圖、Sequence、API spec、NFR 量化、Compliance Matrix、ATAM Scenarios 等）。完整 ADR / Risk Register / Assumption Register 在 W3 完成。

---

## 執行摘要（Executive Summary）

### 北極星指標
**Resolved Service Tasks Under Governance**（受治理條件下完成的服務任務數）。

### 三句口訣（v2 → v3 沿用）

```text
1. Hermes 當學習型大腦；Belief-Driven Runtime 當對話器官；
   Vertical Entity Model 當骨架；Governance 當神經系統。

2. AI 可以持續進步，但每次進步都必須被審核、測試、版本化與回滾；
   Session 內 belief 即時更新，跨 session skill 嚴格治理。

3. 長線護城河不是模型，而是專家被動回饋、垂直 entity model、
   治理系統、評估資料與深度整合。
```

### 五項產品承諾

| 承諾 | 對買方意義 |
| :--- | :--- |
| **Trainable** | 專家可訓練，新人 onboarding 1 週能用 |
| **Deployable** | 可逐步上線：copilot → shadow → 低風險自動化 |
| **Governable** | 可治理與審計，出事可追、可回滾 |
| **Transferable** | 記憶與技能可遷移，不被單一 runtime 鎖死 |
| **Measurable** | 品質與 ROI 可量化（解決率、節省工時、客訴率） |

### Stakeholder 速覽（誰該讀哪幾章）

| Stakeholder | 重點章節 |
| :--- | :--- |
| C-Level / Board / VC | Executive Summary、Part I、Part X §41 Roadmap、§47 ADRs |
| Enterprise Architect | Part III-VI（Data / Application / Integration / Technology） |
| 客戶資安長 | Part VII §26-§29（Threat / Controls / Compliance / Privacy） |
| 法遵長 | §28 Compliance Matrix、§14.7 跨境傳輸 |
| 採購評估委員會 | §10 Business Model、Part VIII NFRs、§34 Cost Architecture |
| 工程主管 | Part IV §15-§19（C4 三層 + Sequence）、附錄 C-E Schema |
| SRE / DevOps | §24 Deployment、§32 Operability、Part X §43 Migration |
| 資料科學家 | §17.6 Training & Eval、§37 AI Behavior CI/CD |
| 客服主管（買方） | §7 Product Definition、§8 Buyer Personas、§44 Success Metrics |

### 一句話最終論點

```text
AI 藍領客服平台不是要創造一個更會聊天的 bot。
它要創造一套可管理的 AI 數位員工制度，
建立在 belief-driven runtime 與 vertical entity model 之上，
由 passive feedback 餵養學習，由 expert governance 守住底線，
由 Reasoning & Cost Router 保住毛利。
```

### 三大陷阱（v2 教訓內化為 v3 治理紅線）

1. 把客服理解成聊天 → 客服是**服務任務**，不是對話表演
2. 把自我學習理解成自動放權 → 企業需要**受控學習**
3. 把模型能力當護城河 → 治理、資料、技能、整合、評估才是護城河
4. **把 utterance trigger 當 skill activation**（v2 補上）→ 必須改為 belief-condition trigger

---

## 目錄總覽

```
封面 / 文件控制 / 執行摘要

Part I    策略基礎（Strategic Foundation）
  §1  Vision & Mission
  §2  Business Context（含市場、系統動態、SWOT）
  §3  Stakeholders & Concerns（ISO 42010）
  §4  Architecture Principles

Part II   商業架構（Business Architecture）
  §5  Business Capability Map
  §6  Value Streams
  §7  Product Definition
  §8  Buyer Personas & Use Cases
  §9  Vertical Wedge & Domain Selection
  §10 Business Model & Pricing

Part III  數據與資訊架構（Data & Information Architecture）
  §11 Conceptual Data Model
  §12 Logical Data Model
  §13 Physical Data Architecture
  §14 Data Governance

Part IV   應用架構（Application Architecture）
  §15 Application Landscape（C4 L1 System Context）
  §16 Container View（C4 L2）
  §17 Component View（C4 L3）— 七層子系統
  §18 Multi-Agent Orchestration
  §19 Sequence Diagrams

Part V    整合架構（Integration Architecture）
  §20 Service Catalog & API Inventory
  §21 Integration Patterns
  §22 External Integrations

Part VI   技術架構（Technology Architecture）
  §23 Technology Stack
  §24 Deployment View
  §25 Reference Architectures

Part VII  安全與合規架構（Security & Compliance）
  §26 Threat Model
  §27 Security Controls
  §28 Compliance Matrix
  §29 Privacy by Design

Part VIII 品質屬性（Quality Attributes / NFRs）
  §30 Performance & Scalability
  §31 Reliability & Availability
  §32 Operability & Observability
  §33 Maintainability & Evolvability
  §34 Cost Architecture
  §35 Quality Attribute Scenarios（ATAM）

Part IX   治理與運營（Governance & Operations）
  §36 Architecture Governance
  §37 AI Behavior CI/CD
  §38 Operations Model
  §39 Capability Maturity Model

Part X    實施與遷移（Implementation & Migration）
  §40 MVP Definition
  §41 Roadmap
  §42 Cold Start Strategy
  §43 Migration & Transition
  §44 Success Metrics

Part XI   風險與決策（Risk & Decisions）
  §45 Risk Register
  §46 Assumption Register
  §47 Architecture Decision Records（ADRs）
  §48 RL 導入決策

Part XII  附錄（Appendices）
  A. Glossary
  B. 垂直 Entity Model 範例（電子鎖維修派工）
  C. Belief Schema v3 JSON Schema
  D. AgentRuntimeAdapter OpenAPI 規格
  E. Skill Schema 範例
  F. Compliance Matrix 完整表
  G. ATAM Quality Attribute Scenarios 集合
  H. References & Standards
  I. Change Log
  J. Distribution & Approval Sign-off
```

---

# Part I — 策略基礎（Strategic Foundation）

---

## §1 Vision & Mission

> **Reader**：C-Level / Board / VC / 早期員工
> **Decision**：是否投入、是否加入、是否相信長線方向
> **Evidence Needed**：北極星指標、五項產品承諾、非目標清單

### 1.1 Vision Statement

```text
建立服務業 AI 數位員工的作業系統，
讓任何企業都能僱用、訓練、複訓、派工、審計一支可治理的 AI 服務員工。
```

### 1.2 Mission Statement

```text
把 Hermes-like agent 包裝成可治理、可訓練、可規模化、可獲利的
AI 藍領客服平台，先在電子鎖維修派工垂直驗證，再擴張到服務業生態。
```

### 1.3 北極星指標：Resolved Service Tasks Under Governance

不採用「訊息數」「對話數」「自動化率」作為主指標——三者皆可能與真實價值脫鉤（訊息多 = 客戶更困惑；自動化高 = 真人技能退化）。

**主指標**：**Resolved Service Tasks Under Governance**——每個受治理條件下完成的服務任務。

### 1.4 非目標（Non-Goals）

| 非目標 | 原因 |
| :--- | :--- |
| 純 FAQ bot | FAQ 只能回答，不能完成服務 |
| Prompt wrapper | 沒有版本、測試、權限、審計無法企業化 |
| 無人客服烏托邦 | 高風險場景仍需人類負責 |
| 讓 AI 假裝真人 | 透明告知與責任邊界是信任基礎（EU AI Act §50） |
| Cross-tenant 自動學習 | 客戶資料權屬與合規邊界 |
| **Utterance-trigger 的 skill router** | 與第一性原理 F1 衝突，必然撞牆 |

### 1.5 詳細產品定位

整合後的產品定位：

```text
Trainable AI Service Worker on Belief-Driven Runtime,
Governed by Expert-Audited Skill Registry over Vertical Entity Model.
```

---

## §2 Business Context

> **Reader**：C-Level / VC / 客戶決策層 / 競品分析者
> **Decision**：是否值得在這個時機進場、競爭格局如何
> **Evidence Needed**：宏觀市場訊號、系統動態、SWOT、護城河可建設性

### 2.1 市場宏觀訊號

- **Gartner 2024-12**：85% 客服領導者將在 2025 年探索或試點 customer-facing conversational GenAI
- **Gartner 2025-03**：到 2029 年 Agentic AI 將自主解決 80% 的常見客服問題，帶來 30% 營運成本下降

但這些是市場機會訊號，不是護城河訊號。**模型能力會商品化，企業信任不會商品化**。

策略判斷：

```text
LLM 是引擎。
客服流程是道路。
企業治理是交通規則。
訓練資料與技能版本是地圖。
真正的公司價值在道路、規則、地圖與營運網路，不在單顆引擎。
```

### 2.2 在地市場觀察

- LINE 在台灣藍領場景近壟斷
- 中小企業客服 SOP 數位化滲透率仍低
- 服務業勞動力短缺壓力持續
- 客服流動率高、訓練成本高（首月離職 30%+，訓練週期 2-4 週）

### 2.3 系統動態（Causal Loop Diagrams）

#### 負反饋環 A：自動化率過度提升的反噬

```
自動化率 ↑ → 真人處理量 ↓ → 真人例外經驗 ↓
  → 例外品質 ↓ → 客訴 ↑ → 信任 ↓
  → 客戶要求降低自動化率 → 自動化率 ↓
```

**對沖**：保留「人工 shadow review」固定比例（如 5%），自動化率設天花板（如 70%）。

#### 負反饋環 B：Skill 爆炸

```
expert feedback 累積 ↑ → skill 變種數量 ↑ → trigger 衝突 ↑
  → orchestrator 複雜度 ↑ → 維護成本 ↑ → 迭代速度 ↓
  → 新需求積壓 ↑ → 變種數量 ↑
```

**對沖**：Skill deprecation policy（每季淘汰使用率 <1% 的 skill）、skill consolidation review、trigger 改為 belief condition。

#### 負反饋環 C：Eval 鮮度衰退

```
產品上線 → 客戶語料演化 → eval set 過時但未被偵測
  → regression test 失效 → 上線翻車 → 客戶不信任 → 業務萎縮
```

**對沖**：Eval freshness audit——定期把線上對話與 eval set 做 distribution 對比，超閾值時自動 flag。

#### 正反饋環：Passive Label Flywheel（要主動養成）

```
真人客服送出回覆 → 與 AI 建議自動 diff
  → 高 diff 進 review queue → 30 秒 expert touch
  → 進 skill proposal → eval → release
  → AI 建議品質 ↑ → 真人需要修改的比例 ↓
  → 真人標註負擔 ↓ → 標註意願 ↑
```

### 2.4 競爭格局（SWOT）

| 維度 | 內容 |
| :--- | :--- |
| **Strengths** | (1) Hypothesis-driven runtime 在邊界 case 比 classifier-router 強；(2) 治理層完整可進企業；(3) 垂直 entity model 形成資料壁壘；(4) Passive labeling 規模化路徑；(5) Reasoning & Cost Router 兼顧品質與毛利 |
| **Weaknesses** | (1) Cold start 嚴重——新 tenant 沒資料；(2) 團隊規模能否支撐 12+ 模組 × 7 層架構；(3) Hermes 0.x 上游風險；(4) Entity model 工程化每個垂直都要重做；(5) Onboarding 必須有 professional services，難純 SaaS |
| **Opportunities** | (1) 中小企業客服 SOP 數位化滲透率仍低；(2) LINE 在台灣藍領場景幾近壟斷；(3) Gartner 預測背書；(4) LLM 邊際成本下降；(5) 服務業勞動力短缺壓力 |
| **Threats** | (1) Salesforce Service Cloud / Freshworks / Intercom Fin Agent 等已在做；(2) LLM provider 自己出 enterprise agent runtime（OpenAI Custom GPT Enterprise / Anthropic on Bedrock + AWS Connect）；(3) 客戶資料權屬阻擋 cross-tenant skill 複用；(4) 法規收緊（EU AI Act / 生成式 AI 標示義務） |

### 2.5 不能當護城河的東西

| 看似護城河 | 為何不可靠 |
| :--- | :--- |
| 接入某個 LLM | 每個競爭者都能接 |
| Prompt 技巧 | 容易複製、不穩定 |
| 單一聊天入口 | LINE / WhatsApp / Web Chat 都只是通道 |
| 一般 RAG | 向量搜尋已商品化 |
| Demo 很漂亮 | 企業買的是穩定、責任、ROI |

### 2.6 應該建立的護城河（按可建設性 × 防禦力排序）

| # | 護城河 | 建設成本 | 防禦力 | 建設順序 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Vertical Entity Model + Skill Graph | 中 | 高 | Phase 1 起 |
| 2 | Passive Feedback Flywheel 資料資產 | 中 | 高 | Phase 2 起 |
| 3 | Evaluation Harness（含 freshness 機制） | 低 | 中 | Phase 1 起 |
| 4 | 多租戶治理 + 審計合規 | 中 | 高 | Phase 3 起 |
| 5 | 工具/業務系統整合深度 | 高 | 高 | Phase 3 起 |
| 6 | Reasoning & Cost Router（毛利護城河） | 中 | 中 | Phase 2 起 |
| 7 | 垂直法規與品牌 policy 庫 | 中 | 中 | Phase 2 起 |

---

## §3 Stakeholders & Concerns（ISO/IEC/IEEE 42010）

> **Reader**：所有 stakeholder（自我定位用）
> **Decision**：「我關心的議題在哪些章節能找到答案」
> **Evidence Needed**：Stakeholder × Concern × View 三向對應矩陣

### 3.1 Stakeholder 清單

| Stakeholder | 角色定位 | 主要 Pain |
| :--- | :--- | :--- |
| **企業買方**：中小企業客服主管 / 連鎖品牌客服經理 / 服務業老闆 | 採購決策 | 省人、省訓練、可解釋、不出包 |
| **客戶資安長（CISO）** | 安全評估 | Tenant isolation、PII、Audit、Threat model |
| **法遵長（CCO）** | 合規評估 | 個資法、消保法、垂直法規、EU AI Act |
| **採購評估委員會** | RFP 評選 | SLA、TCO、ROI、退場條件 |
| **企業內一線客服** | 日常使用 | 工具好不好用、會不會被 AI 取代 |
| **企業內客服主管** | 運營監督 | 出事能追、能改 SOP、能解釋 |
| **終端消費者** | 體驗對象 | 問題能解決、被當人對待、知道在跟 AI 對話 |
| **平台運營團隊** | Build & Run | 維護成本、迭代速度、可觀測 |
| **SRE / DevOps** | 可靠性 | Deployment、Monitoring、Incident response |
| **平台安全團隊** | 主動防禦 | Prompt injection、Memory poisoning |
| **資料科學家 / ML 工程師** | 學習迴圈 | Eval set、Drift、Labeling pipeline |
| **LLM 供應商** | 上游依賴 | 並非利益相關方但構成限制 |
| **整合夥伴**（CRM / ERP / POS 廠商） | 通路 | API 穩定、商業共榮 |
| **監管機構** | 法定 | EU AI Act、個資保護機關、消保官 |
| **C-Level / Board / VC** | 治理層 | 北極星、護城河、競爭格局、Unit Economics |

### 3.2 Concerns Matrix

| Stakeholder | 功能性 | 品質性 | 成本 | 合規 | ROI |
| :--- | :---: | :---: | :---: | :---: | :---: |
| 企業買方 | ✓✓✓ | ✓✓ | ✓✓✓ | ✓✓ | ✓✓✓ |
| 客戶 CISO | ✓ | ✓✓ | — | ✓✓✓ | — |
| 法遵長 | — | ✓ | — | ✓✓✓ | — |
| 採購委員會 | ✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ | ✓✓✓ |
| 一線客服 | ✓✓✓ | ✓✓ | — | — | ✓ |
| 客服主管 | ✓✓✓ | ✓✓ | ✓ | ✓ | ✓✓ |
| 終端消費者 | ✓✓ | ✓✓✓ | — | ✓✓ | — |
| 平台運營 | ✓✓✓ | ✓✓✓ | ✓✓ | ✓ | ✓ |
| SRE/DevOps | ✓ | ✓✓✓ | ✓✓ | — | — |
| 平台安全 | — | ✓✓✓ | — | ✓✓✓ | — |
| 資料科學家 | ✓✓ | ✓✓✓ | ✓ | ✓ | — |
| C-Level/Board | ✓ | ✓ | ✓✓ | ✓✓ | ✓✓✓ |

### 3.3 Viewpoints & Views 對應表

| Concern | 提供答案的章節（Views） |
| :--- | :--- |
| 功能性能力 | §5 Capability Map、§17 Component View、§20 Service Catalog |
| 對話品質 | §17.2 Conversation Runtime、§19 Sequence、§35 ATAM |
| 可靠性 / SLA | §24 Deployment、§31 Reliability、§32 Observability |
| 成本（TCO） | §10 Business Model、§34 Cost Architecture |
| 多租戶隔離 | §13 Physical Data、§14 Data Governance、§27.2 Tenant Isolation |
| PII / Audit | §14.5 PII Lifecycle、§27.5 Audit Logging、§28 Compliance Matrix |
| 法規對應 | §28 Compliance Matrix、§29 Privacy by Design |
| 升級路徑 | §39 Capability Maturity Model、§41 Roadmap |
| 退場條件 / 鎖定風險 | §17.3.1 AgentRuntimeAdapter、§43 Migration |
| 訓練學習迴圈 | §17.6 Training & Eval、§37 AI Behavior CI/CD |
| Founder/VC 戰略 | Executive Summary、Part I |

---

## §4 Architecture Principles

> **Reader**：Architect / 開發團隊 / Code Reviewer
> **Decision**：任何設計取捨時的紅線
> **Evidence Needed**：每條原則的「為什麼」與「不遵守會怎樣」

### 4.1 三條不可化約事實（F1/F2/F3）

把客服對話拆到不能再拆，剩下三件事：

| 事實 | 內容 | 對架構的意涵 |
| :--- | :--- | :--- |
| **F1** | 客戶資訊不對稱：客戶往往不知道自己真正的問題是什麼 | Runtime 不能假設 utterance 是 ground truth；要保留質疑與覆寫表面意義的能力 |
| **F2** | AI 資訊不對稱：AI 看不到客戶真實情境、過去歷史、心理狀態 | Runtime 必須有 belief 機制，且 belief 是 partial、可修正、可審計的 |
| **F3** | 對話本質是雙向降低不確定性 | 每一輪 action 選擇標準是「降低不確定性的速度 × 客戶體驗成本」加權 |

### 4.2 五個設計原則（P1-P5）

| # | 原則 | 解釋 |
| :--- | :--- | :--- |
| P1 | Runtime 核心物件是 **Hypothesis**，不是 Intent | Intent 是 utterance 級標籤；hypothesis 是對情境的整體推測，跨輪累積 |
| P2 | Action 由 **Belief** 驅動，不由 utterance 觸發 | 同一個 utterance 在不同 belief 下該做不同事 |
| P3 | 每一輪都要顯式做 **Calibration** | 客戶反應同時是下一輪 input 與對上一輪 belief 的隱性 feedback |
| P4 | Belief 必須**結構化、可審計** | JSON-like schema，不能藏在 LLM 內部 |
| P5 | 學習區分「**session-scoped** belief 即時更新」與「**cross-session** skill 治理發布」 | 兩者治理強度不同，不能混為一談 |

### 4.3 治理原則（Gartner Pace-Layered）

| 層 | 對應系統 | 變動速度 | 治理強度 |
| :--- | :--- | :--- | :--- |
| **System of Record (SoR)** | Skill Registry、Knowledge Base、Audit Log | 慢 | 強治理（CI/CD、版本、回滾） |
| **System of Differentiation (SoD)** | Vertical Entity Model、Brand Policy、Tenant Memory | 中 | 中治理（per-tenant 審核） |
| **System of Innovation (SoI)** | Belief State、Session Memory、In-flight Hypothesis | 快 | 弱治理（session 內可變） |

### 4.4 工程原則

| 原則 | 解釋 |
| :--- | :--- |
| **YAGNI** | 不為假想需求設計 |
| **Single Source of Truth** | Skill / Knowledge / Memory / Belief 各有明確 SoT |
| **Fail-Fast** | 邊界與 schema 違反 → 立即報錯而非靜默 |
| **Reversibility** | 所有變更需可回滾；不可逆操作需明確 gate |
| **Pluggable Runtime** | Hermes 等 harness 必須透過 Adapter，不直接耦合 |

### 4.5 與既有產業標準對應

| 標準 | 採用範圍 |
| :--- | :--- |
| NIST AI RMF GenAI Profile 2024-07-26 | Threat / Control 對應（§26-§27） |
| OWASP Top 10 for LLM Applications | §26.2 LLM-specific threats |
| ISO 27001 | §27 Security Controls 基底 |
| EU AI Act Article 50 | §29 Privacy by Design、§28.3 透明告知 |
| ISO/IEC/IEEE 42010:2022 | 本白皮書整體結構 |
| TOGAF 9.2 ADM | Part I-X 編排 |

---

# Part II — 商業架構（Business Architecture）

---

## §5 Business Capability Map

> **Reader**：CTO / 業務團隊 / 客戶 Enterprise Architect
> **Decision**：平台提供哪些 business capabilities、與既有客服系統如何 fit
> **Evidence Needed**：L1/L2/L3 能力分解 + Fit-Gap

### 5.1 L1 Capabilities

```text
┌─────────────────────────────────────────────────────────┐
│                AI Service Worker Platform                │
├─────────────────────────────────────────────────────────┤
│ L1.1  Customer Service Operations                       │
│ L1.2  AI Workforce Management                           │
│ L1.3  Service Governance                                │
│ L1.4  Continuous Learning                               │
│ L1.5  Business Integration                              │
└─────────────────────────────────────────────────────────┘
```

### 5.2 L2 分解

| L1 | L2 |
| :--- | :--- |
| **L1.1 Customer Service Operations** | Inbound Conversation Handling / Intent Resolution / Task Execution / Human Escalation / Sentiment & Crisis Management |
| **L1.2 AI Workforce Management** | Hire（onboard tenant） / Train（skill development） / Supervise（governance） / Promote（maturity level up） / Retire（deprecate） |
| **L1.3 Service Governance** | Tenant Isolation / Brand Policy / Risk-Tiered Tool Use / Audit & Replay / Compliance Reporting |
| **L1.4 Continuous Learning** | Passive Diff Capture / Expert Review / Skill Proposal / Evaluation / Canary Release |
| **L1.5 Business Integration** | CRM / ERP / Ticket / Order / Notification / Channel Gateway |

### 5.3 與既有客服系統的 Fit-Gap

`[TBD-W2]` — 待補：與 Zendesk / Salesforce Service Cloud / Freshdesk / Intercom Fin 的能力對映表，標出我們不做的、互補的、競爭的。

---

## §6 Value Streams

> **Reader**：產品 / 業務 / Onboarding 團隊
> **Decision**：怎麼跟客戶現有 process 對接
> **Evidence Needed**：每條 value stream 的觸發、階段、價值交付

### 6.1 End-Customer Value Stream

```text
[消費者發訊]
   ↓
[Channel Gateway 正規化]
   ↓
[Hypothesis Engine 形成 belief]
   ↓
[Reasoning & Cost Router 選策略]
   ↓
[Skill / Tool 執行]
   ↓
[回覆 或 轉人工]
   ↓
[Customer Outcome]
```

**價值交付**：問題解決、時間節省、體驗一致。

### 6.2 Enterprise Buyer Value Stream

```text
[需求識別] → [採購評估] → [PoC] → [Onboarding] →
[Phase 1 Copilot] → [Phase 2 Shadow] → [Phase 3 自動化] →
[續約 / 擴展]
```

**價值交付**：人力節省、訓練週期縮短、品質一致、可審計。

### 6.3 Expert Trainer Value Stream

```text
[Passive Diff Engine 偵測高差異案例]
   ↓
[Quick Review Card 30 秒判斷]
   ↓
[Skill Proposal 產生]
   ↓
[Sandbox Eval / Regression]
   ↓
[Canary Release 5%]
   ↓
[Full Release 或 Rollback]
```

**價值交付**：AI 員工持續改善而不破壞穩定性。

### 6.4 Cross-tenant Skill Pack Value Stream

```text
[Tenant A 累積 Skill]
   ↓
[匿名化 / 抽出 SOP 結構]
   ↓
[Vertical Skill Pack 提案]
   ↓
[Domain Expert 審核]
   ↓
[Marketplace 上架]
   ↓
[Tenant B/C/... 採用 + 抽成]
```

**價值交付**：Cold start 加速、垂直生態系成形。

---

## §7 Product Definition

> **Reader**：產品 / 行銷 / 業務 / 新員工
> **Decision**：怎麼一句話講清這是什麼
> **Evidence Needed**：費曼測試三句話 + 工作類型分類

### 7.1 一句話定位

```text
AI 藍領客服平台是一套可訓練、可派工、可審計、可複訓、
基於垂直 entity model 與信念驅動運行時的 AI 數位員工作業系統。
```

### 7.2 五項產品承諾

（同 Executive Summary，此處列為治理紅線）

### 7.3 客服五種工作類型

| 工作類型 | 例子 | AI 風險 | 對應防線 |
| :--- | :--- | :--- | :--- |
| 解釋 | 說明規則、費用、流程 | 幻覺、過度承諾 | RAG grounding、信心門檻、報價類強制轉人工 |
| 查詢 | 查訂單、查工單、查會員 | 權限錯誤、資料外洩 | 身份驗證、PII redaction、tenant 隔離 |
| 判斷 | 退款資格、補件條件、升級條件 | 規則誤用、責任不明 | Risk-tiered tool、人工批准、規則引擎 fallback |
| 執行 | 建工單、改預約、派單 | 工具越權、錯誤操作 | 最小權限、行為 trace、可回滾 |
| 安撫 | 處理抱怨、延遲、衝突 | 情緒升級、品牌損害 | 情緒偵測、強制轉人工、話術 policy |

```text
不是回答引擎，而是工作引擎。
不是 FAQ bot，而是 SOP worker。
不是 prompt wrapper，而是 governed digital labor platform。
```

### 7.4 費曼測試：給非技術買家的三句話

```text
1. 我們不是 chatbot。我們是「會學習的 AI 員工」——你怎麼訓練新人，就怎麼訓練它。
2. 它先在旁邊看你的客服怎麼回，慢慢學會 70% 的重複問題自動處理，剩下 30% 才轉給真人。
3. 它做的每個決定都有紀錄，你的客服主管可以一鍵看到「為什麼這樣回」、可以一鍵回滾。
```

對應三個核心：trainable、graduated automation、governed。

---

## §8 Buyer Personas & Use Cases

> **Reader**：產品 / 業務 / 行銷
> **Decision**：賣給誰、為了什麼任務（JTBD）
> **Evidence Needed**：Persona 痛點與量化指標、Top 10 Use Cases

### 8.1 Buyer Personas

**真正的買方不是「客服人員」也不是「客戶」**，是：

```text
中小企業客服主管 / 連鎖品牌客服經理 / 服務業老闆
```

**痛點與 KPI**：

| 痛點 | 量化指標 |
| :--- | :--- |
| 客服人員流動率高、訓練成本高 | 訓練週期 2-4 週、首月離職率 30%+ |
| LINE 一線回覆量大但重複 | 70%+ 對話是重複問題 |
| 客服回覆品質參差 | 同一問題不同人不同答案 |
| 旺季人力撐不住 | 春節、雙 11、年中慶 |
| 老闆要 ROI 但客服難量化 | 缺乏跨組可比較數據 |

**Jobs-To-Be-Done**：
1. 省人（減少 1-2 個人力或 cover 旺季尖峰）
2. 省訓練（新人 onboarding 從 4 週縮到 1 週）
3. 可解釋（出事能追蹤、能解釋給客戶）
4. 不出包（誤承諾、誤承擔、誤洩漏的代價遠大於省下來的人力）

### 8.2 Top Use Cases

`[TBD-W2]` — 待補：垂直具體場景 10 條，每條含「對話樣本 / Belief 範例 / Skill / Tool / 預期 outcome」。先行範例見附錄 B。

### 8.3 反例：哪些場景平台不適合

| 不適合 | 原因 |
| :--- | :--- |
| 純法律諮詢 | L4 不可自動 |
| 保險核保 | 法規門檻太高、§28 列為禁止 |
| 醫療診斷 | 同上 |
| 高額財務承諾 | 同上 |
| 完全沒 SOP 的創意客服 | 沒有可學習的範式 |

---

## §9 Vertical Wedge & Domain Selection

> **Reader**：產品 / 業務 / 投資人
> **Decision**：先打哪個垂直、為什麼
> **Evidence Needed**：選擇矩陣、entity 可工程化證據、擴張路徑

### 9.1 Wedge 選擇邏輯（v2 修正）

v1 把選擇邏輯停在「市場面」（高重複、低法律風險、ROI 易量化）。**v2 引入更關鍵的維度**：「該垂直的 entity model 能不能工程化」。沒有 entity model：
- Skill 寫得再好接不上業務資料
- Tool calling 沒有 schema 可遵循
- Belief 的 dimensions 沒有 domain anchor
- RAG 沒有 entity-aware retrieval
- Audit trace 沒有 business object 可追蹤

### 9.2 Wedge 選擇矩陣

| 場景 | Entity 複雜度 | SOP 標準化度 | 法規風險 | B2B/B2C | ROI 可量化 | 推薦度 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 電商售後（退換貨） | 中 | 高 | 中（消保法） | B2C | 高 | ★★★★ |
| **電子鎖維修派工** | **高** | **高** | **低** | **B2B+B2C** | **高** | **★★★★★** |
| 餐飲訂位 | 低 | 高 | 低 | B2C | 中 | ★★★ |
| SaaS 客服 | 中 | 中 | 低 | B2B | 中 | ★★★ |
| 物業客服 | 高 | 中 | 中 | B2B | 中 | ★★ |
| 保險理賠初審 | 高 | 高 | 高 | B2C | 高 | ★★（法規門檻太高） |

**Phase 1 Wedge**：**電子鎖維修派工**。理由：entity 複雜但可工程化、SOP 標準化、B2B+B2C 並存可分階段切入、agent_v2 已在驗證此場景。

### 9.3 Entity Model 工程的最小可行交付（硬 gate）

選定 wedge 後，**動 code 前必須**先交付以下七工件（完整內容見附錄 B）：

| # | 工件 | 內容 |
| :--- | :--- | :--- |
| 1 | Entity Dictionary | 該垂直的核心物件清單與屬性 |
| 2 | Event Catalog | 該垂直的關鍵事件與觸發條件 |
| 3 | State Machine | 主要 entity 的狀態轉移圖 |
| 4 | SOP Graph | 每個 SOP 對應的 entity 操作序列 |
| 5 | Belief Schema Extension | 該垂直特有的 belief dimensions |
| 6 | Tool Permission Matrix | 每個工具對應的 entity 操作權限與風險等級 |
| 7 | Vertical Glossary | 領域術語對照表 |

**沒交付這七件不進 Phase 1**。

### 9.4 垂直擴張路徑

```text
電子鎖 → 印章 → 開鎖 → 汽車鑰匙 → 物業
（公共資產相關藍領服務群）
```

每垂直需重做七工件，但可重用平台的 Layer 1-6。

---

## §10 Business Model & Pricing

> **Reader**：採購評估委員會 / CFO / 業務
> **Decision**：定價結構、TCO、Payback、Outcome-based 可行性
> **Evidence Needed**：定價模型、Unit Economics、與推理層級的對應

### 10.1 定價模型

| 模型 | 適用 | 備註 |
| :--- | :--- | :--- |
| Seat-based | Copilot 階段 | 按客服人員數 |
| Usage-based | 自動化處理量 | 按 resolved task |
| Tenant platform fee | 企業多租戶與治理 | 固定月費 |
| Skill pack fee | 垂直產業技能包 | 一次性 + 月費 |
| Integration fee | 深度系統整合 | 一次性 |
| Outcome-based | 高成熟客戶 | 以解決率 / 節省工時計價 |
| **Onboarding & Professional Services** | **新 tenant 必收** | **SOP 訪談、Entity Model 客製化、Calibration session** |

**Professional Services 是必然存在的收入項**，不是可選。Cold start 沒這個就沒辦法做。

### 10.2 定價層級對應推理層級

| 方案 | 推理策略 |
| :--- | :--- |
| Basic | FAQ、RAG、小模型、低風險工具 |
| Pro | Skill workflow、中模型、更多工具整合 |
| Enterprise | 高階模型、multi-agent critique、客製 evaluation、SLA |
| Regulated | 強審計、人工批准、資料保留、合規報告 |

### 10.3 Unit Economics

`[TBD-W2]` — 待補：
- CAC（含 Professional Services 成本）
- LTV（按定價層級）
- Gross Margin（含 Token cost 變動）
- Payback Period
- 與 Cost Architecture（§34）的對應

### 10.4 Cross-tenant Skill 抽成模型

- Default 不跨 tenant 共享
- Tenant 可選擇「貢獻為產業共通 skill」（明確同意 + 匿名化 + 抽成）
- 跨 tenant 共享只在「明確匿名化的 SOP 結構」層級，不在「客戶對話 raw data」層級

---

# Part III — 數據與資訊架構（Data & Information Architecture）

---

## §11 Conceptual Data Model

> **Reader**：Data Architect / Engineering Lead / 新工程師
> **Decision**：理解平台核心領域物件與關係
> **Evidence Needed**：ER 概念圖、物件職責、與 K/M/S 三分立的對應

### 11.1 核心領域物件

| 物件 | 本質 | SoT |
| :--- | :--- | :--- |
| **Tenant** | 企業客戶 | Tenant Manager |
| **User** | 終端消費者（含 author/owner 雙身份）| Identity Manager |
| **Conversation** | 對話 session | Conversation Manager |
| **Turn** | 對話單輪 | Conversation Manager |
| **Belief** | 結構化 hypothesis state | Belief State Manager（session-scoped） |
| **Skill** | 可執行 SOP 單元（belief-condition trigger） | Skill Registry |
| **Knowledge** | 正式事實（FAQ / 政策 / 規格） | Knowledge Base |
| **Memory** | 過去經驗與偏好 | Memory Router |
| **Trace** | 全 turn 審計紀錄 + belief snapshot | Audit Log |
| **Cost Record** | per turn / per task 成本 | Cost Meter |
| **WorkOrder / Device / Customer / ...** | 垂直 entity（依 wedge）| Vertical Entity Model |

### 11.2 ER 概念圖

```text
Tenant 1───*  User
Tenant 1───*  Conversation
Conversation 1───*  Turn
Turn 1───1  Belief（snapshot）
Turn 1───*  Trace
Turn 1───*  ToolCall
Skill *───* BeliefCondition
Skill 1───*  ToolPermission
Skill 1───1  RiskLevel
Knowledge *───* Tenant（with scope policy）
Memory *───* Tenant（with scope policy）
Memory 1───1  RetentionPolicy
Trace 1───1  CostRecord
```

完整 ER 與物理 schema 見 §13 與附錄 C-E。

### 11.3 K / M / S 三者分立

不能把所有內容都塞進 skill 然後讓 agent 自行判斷。短期看似簡單，長期會導致四種混亂：

| 混亂 | 例子 | 後果 |
| :--- | :--- | :--- |
| 事實與流程混在一起 | 退款天數和退款操作步驟寫同一個 skill | 政策更新時難以維護 |
| 通用規則與租戶例外混在一起 | A 品牌優惠規則被 B 品牌使用 | 多租戶污染 |
| 單次事件與長期知識混在一起 | 某客戶一次抱怨被當成永久規則 | 行為漂移 |
| 可回答資訊與可執行動作混在一起 | FAQ 和退款工具權限放一起 | 越權操作風險 |

三者應該這樣切：

| 類型 | 本質 | 例子 | 主要治理方式 |
| :--- | :--- | :--- | :--- |
| Knowledge | 什麼是真的 | SOP、FAQ、產品規格、價格、退款政策 | 文件版本、來源引用、有效期限 |
| Memory | 發生過什麼、誰偏好什麼 | 某客戶歷史、某 tenant 慣例、過去案例 | scope、retention、PII、tenant 隔離 |
| Skill | 遇到情境時怎麼做 | 退貨流程、補件流程、升級工單流程 | 版本、測試、權限、回滾、belief condition trigger |

**判斷準則**：

```text
如果它描述真相，放 Knowledge。
如果它描述過去或偏好，放 Memory。
如果它描述可執行流程，放 Skill。
如果它會改變外部系統，必須進 Tool & Workflow Layer。
```

---

## §12 Logical Data Model

> **Reader**：Data Architect / 後端工程師 / 資料科學家
> **Decision**：實作各 schema 細節
> **Evidence Needed**：完整 schema（Belief / Skill / Memory / Trace + Vertical Entity）

### 12.1 Vertical Entity Model（電子鎖維修派工，七工件摘要）

完整內容見附錄 B。摘要：

- **Entity Dictionary**：Device / Customer / ServiceRequest / WorkOrder / Technician / Part / SLAContract
- **Event Catalog**：ServiceRequestCreated / DeviceIdentified / WorkOrderAssigned / TechnicianDispatched / PartReserved / ServiceCompleted / BillingSettled
- **State Machine**：WorkOrder（pending → assigned → in_progress → completed）
- **Belief Schema Extension**：brand_known / model_known / device_location_known / symptom_classified / warranty_status / urgency_modifier / participant_role
- **Tool Permission Matrix**：L0-L4 對應 lookup / create / assign / cancel / refund 操作
- **Vertical Glossary**：「卡卡的」「鎖頭歹去」「嗶嗶叫」對應內部 enum

### 12.2 Belief Schema v3（含 likely_misframe / temporal / spatial）

```json
{
  "turn_id": "t-008",
  "hypotheses": [
    {
      "id": "h1",
      "description": "客戶在比較電子鎖品牌，未擁有設備，無強迫升級需求",
      "confidence": 0.78,
      "evidence": ["首次提及『想看』", "未提及型號或故障"],
      "contradicting_evidence": [],
      "likely_misframe": null,
      "dimensions": {
        "primary_intent": "pre_sales",
        "ownership_status": "not_owned",
        "knowledge_level": "novice",
        "underlying_goal": "選擇適合的電子鎖",
        "urgency": "low",
        "cost_sensitivity": 0.3,
        "temporal_context": "now",
        "spatial_context": "unknown"
      },
      "required_to_act": [],
      "recommended_action_if_chosen": "提供主流品牌與分類"
    },
    {
      "id": "h2",
      "description": "客戶想了解售後維修網絡",
      "confidence": 0.10,
      "evidence": ["可能性存在但無直接訊號"],
      "contradicting_evidence": ["明確說『還沒有買』"]
    }
  ]
}
```

**關鍵欄位**：

- `likely_misframe`：客戶可能誤判了什麼。這是 hypothesis-driven 與 classifier 的根本差異點。例：「我的鎖怪怪的」+ `likely_misframe = 客戶可能把電池快沒電誤判為鎖故障` → COMMIT「請先試著替換電池」
- `contradicting_evidence`：顯式記錄反證，避免 confirmation bias
- `temporal_context / spatial_context`：承接 §7.4 多模態需求

完整 JSON Schema 見附錄 C。

### 12.3 Skill Schema

| 欄位 | 說明 |
| :--- | :--- |
| Skill ID / Name / Version / Owner | 基本識別 |
| Tenant Scope / Domain Scope | 適用範圍 |
| **Belief Condition Trigger** | **belief 滿足條件即啟用（v2 取代 keyword trigger）** |
| Input Schema / Output Schema | 資料契約 |
| Tool Permissions | 可用工具與權限 |
| Risk Level（L0-L4） | 風險分級 |
| Human Approval Required | 是否需人工批准 |
| Test Cases / Eval Suite | 測試套件 |
| Rollback Version | 可回滾版本 |
| **Deprecation Policy** | **使用率/品質低於門檻自動 deprecate** |
| **Last Eval Date / Freshness** | **eval set 鮮度** |

**Belief Condition Trigger 範例**：

```yaml
skill: refund_eligibility_check
trigger:
  primary_intent: "support"
  ownership_status: "already_owned"
  brand_known: true
  urgency: ["medium", "high"]
```

完整 Skill Schema 見附錄 E。

### 12.4 Memory Schema（六層）

| 記憶類型 | 說明 | 學習方式 | 跨 tenant 共享 |
| :--- | :--- | :--- | :--- |
| Global Memory | 平台共用安全政策、客服原則 | 嚴格審核 | 是 |
| Domain Memory | 產業知識（維修、餐飲、保固） | 專家審核 | 是（同產業） |
| Tenant Memory | 某企業客戶的 SOP、品牌話術 | 租戶內審核 | 否 |
| Workflow Memory | 特定流程的操作經驗 | 測試後發布 | 否 |
| User Memory | 終端客戶偏好與歷史 | 明確同意與保留政策 | 否 |
| Incident Memory | 錯誤、客訴、風險事件 | 安全團隊審核 | 部分匿名化後可分享 |

### 12.5 Trace / Audit Schema

每 turn 必寫入：
- `turn_id / conversation_id / tenant_id / user_id`
- `utterance / channel / normalized_input`
- `belief_snapshot`（§12.2）
- `action_taken`（COMMIT / PROBE / EXPLORE / ESCALATE）
- `skill_id / skill_version`
- `tool_calls`（含 input / output / status）
- `response_sent`
- `cost_record`（token / API / human-review）
- `risk_flags`（PII / injection / sensitive）

---

## §13 Physical Data Architecture

> **Reader**：DBA / SRE / Data Engineer
> **Decision**：儲存技術選型、分片策略、保留政策、DR
> **Evidence Needed**：技術選型 rationale、tenant isolation 設計、retention 表

### 13.1 儲存技術選型

`[TBD-W2]` — 待補：完整選型表（含 rationale）。建議草稿：

| 資料類型 | 技術 | 理由 |
| :--- | :--- | :--- |
| Tenant / User / Conversation / Turn | PostgreSQL（row-level security） | 結構化、ACID、tenant isolation 成熟 |
| Belief Snapshot / Trace | PostgreSQL JSONB + 冷儲存 S3 | 結構化查詢 + 大量歷史 |
| Knowledge / RAG | Vector DB（pgvector / Qdrant） | Entity-aware retrieval |
| Skill Registry | Git-backed + PostgreSQL index | 版本化、可 diff |
| Memory (curated) | SQLite FTS5（per-tenant）或 PostgreSQL FTS | 沿用 Hermes pattern |
| Queue | Redis Streams / NATS | 低延遲、可重放 |
| Cache | Redis | Prompt cache、Tool result cache |
| Audit Log | Append-only PostgreSQL + S3 | 不可篡改 |
| Object（圖片、語音） | S3-compatible | OCR / multimodal input |

### 13.2 Partition / Sharding Strategy

- **Tenant-level isolation**：所有業務表必含 `tenant_id`；row-level security 強制過濾
- 大 tenant 可獨立 schema 或獨立 DB
- Vector DB 按 tenant 分 namespace

### 13.3 Retention Policy

`[TBD-W2]` — 待補完整表。原則：

| 資料 | 保留期 |
| :--- | :--- |
| Raw conversation | 90 天（可選 30 天 / 180 天 / 1 年） |
| Trace + Belief snapshot | 與 raw conversation 同步 |
| PII（hash 後） | 視同意期 |
| Skill / Knowledge | 永久（版本化保留） |
| Cost Record | 7 年（會計需求） |
| Audit Log | 5-7 年（合規） |

### 13.4 Backup / DR Strategy

`[TBD-W2]` — 待補：RTO / RPO 目標、跨 region 備援、tenant-level restore 流程。

---

## §14 Data Governance

> **Reader**：CISO / CCO / 法遵 / DPO
> **Decision**：跨 tenant policy、PII lifecycle、跨境傳輸合規
> **Evidence Needed**：Memory Router 決策樹、Drift detection、PII pipeline、Data Lineage

### 14.1 Pace-Layered Governance

| 治理層 | 對象 | 變動成本 | 流程 |
| :--- | :--- | :--- | :--- |
| Session-scoped（SoI） | Belief State | 即時 | 不需審核，session 結束銷毀 |
| Cross-session（SoR） | Skill / Knowledge / Memory（curated）| 高 | 完整 CI/CD（§37） |

```text
AI 可以從所有對話中學。
但 AI 不能邊服務客戶、邊未經審核地改變正式行為。
```

### 14.2 Memory Router 決策樹

```text
Memory Router Decision
- 這是哪個 tenant 的資料？
- 是否包含 PII？
- 是否可以跨使用者使用？
- 是否可以跨 tenant 使用？
- 是否為暫時狀態？
- 是否需要專家審核？
- 是否有 retention policy？
- 是否會污染長期行為？
```

### 14.3 Memory Drift Detection + Snapshot Rollback

長期累積的 memory 會「人格漂移」——bounded curated memory 在多輪 expert correction 後可能洗成怪味道。對策：

- **Memory Snapshot**：每週快照一次，記錄當下記憶 state
- **Drift Score**：定期跑一組 reference question，觀察 AI 回答 distribution
- **Drift Score 超閾值 → 強制 human review 與 snapshot rollback**

### 14.4 PII Lifecycle

| 階段 | 控制 |
| :--- | :--- |
| Ingest | Regex-based 基本層（過 5xx pattern） |
| Ingest | LLM-based 進階層（catch context-dependent PII） |
| Storage | 不可進 Domain Memory 與 Global Memory，只進 User Memory 並標 expiry |
| Audit | **Acceptable false negative rate < 0.1%**，超過要報警並回滾 |
| Right-to-be-Forgotten | 客戶請求 → 跨 tenant search → 標記刪除 → 30 天硬刪除 |

### 14.5 Data Lineage & Provenance

`[TBD-W2]` — 待補：從 raw conversation 到 published skill 的完整資料譜系，含中間 transformation 紀錄。

### 14.6 記憶可遷移性

| 資產 | 可遷移性 | 條件 |
| :--- | :--- | :--- |
| Skills | 高 | 通過 cross-runtime eval |
| SOP Knowledge | 高 | 重新驗證 grounding |
| Evaluation Results | 高 | 標清楚 runtime version |
| Brand Voice Policy | 中 | 重新校準 LLM |
| User-specific Memory | 低 | 需合規與用戶同意 |
| Raw Conversation Logs | 低 | 需審計與保留政策 |

核心原則：

```text
身體可以換，技能可以升級，記憶可以遷移，但權限與責任必須重新驗證。
```

### 14.7 跨境傳輸與資料在地化

`[TBD-W2]` — 待補：
- 台灣個資法、EU GDPR、CN PIPL 的傳輸限制矩陣
- Tenant memory 不可跨地區複製
- Multi-region deployment 對應策略（§24.3）

---

# Part IV — 應用架構（Application Architecture）

---

## §15 Application Landscape（C4 Level 1：System Context）

> **Reader**：Architect / 客戶 EA / 整合夥伴
> **Decision**：系統邊界、外部依賴關係
> **Evidence Needed**：C4 L1 上下文圖 + 邊界說明

### 15.1 System Context

```text
                  ┌────────────────────────────┐
                  │  Customer (End Consumer)   │
                  └────────────┬───────────────┘
                               │ LINE / WhatsApp / Web / Email
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│        AI Blue-Collar Customer Service Platform                │
│                                                                │
└──┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬─────┘
   │       │       │       │       │       │       │       │
   ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼
 [LLM]  [CRM]  [ERP]  [Tick] [POS] [Order][Noti] [BizSys]
 Provider                                                  ▲
                                                           │
                                                  ┌────────┴────────┐
                                                  │  Tenant Admin   │
                                                  │  CS Manager     │
                                                  │  Expert Trainer │
                                                  └─────────────────┘
```

詳細圖（含資料流標示）`[TBD-W2]`。

### 15.2 系統邊界

| 進入點 | 協定 |
| :--- | :--- |
| LINE OA Webhook | HTTPS Webhook |
| WhatsApp Business | Cloud API |
| Web Chat | WebSocket / SSE |
| Email | IMAP / SMTP |
| Tenant Admin Console | HTTPS（Browser） |
| Public API | REST / GraphQL |

| 對外呼叫 | 協定 |
| :--- | :--- |
| LLM Providers | HTTPS（Anthropic / OpenAI / Local） |
| CRM / ERP / POS | REST / GraphQL / Legacy SOAP |
| Notification（Email / SMS / Push） | Provider-specific |
| MCP（Model Context Protocol） | MCP standard |

---

## §16 Container View（C4 Level 2）— 七層架構

> **Reader**：Architect / 開發團隊
> **Decision**：模組劃分、容器間通訊
> **Evidence Needed**：七層架構圖、容器清單、通訊協定

### 16.1 七層架構

```text
┌──────────────────────────────────────────────────────┐
│ Layer 7：Experience Layer                            │
│ Web Chat / LINE / WhatsApp / App / Email / CRM       │
└──────────────────────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────┐
│ Layer 6：Service Governance Layer                    │
│ Identity / Tenant / Brand / Policy / Escalation / SLA│
└──────────────────────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────┐
│ Layer 5：Conversation Runtime Layer（v2 新增）       │
│ Hypothesis Engine / Belief / Action Policy / Calib   │
└──────────────────────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────┐
│ Layer 4：Agent Runtime Layer                         │
│ Hermes Adapter / Tool / Search / Cost Router         │
└──────────────────────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────┐
│ Layer 3：Memory & Skill Layer                        │
│ Memory Router / Skill Registry / Knowledge / RAG     │
└──────────────────────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────┐
│ Layer 2：Training & Evaluation Layer                 │
│ Sandbox / Shadow / Passive Label / Eval / Release    │
└──────────────────────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────┐
│ Layer 1：Infrastructure & Data Layer                 │
│ DB / Queue / Cache / Vector / Object / Audit / Cost  │
└──────────────────────────────────────────────────────┘
```

### 16.2 容器級組件清單

| 模組 | 責任 |
| :--- | :--- |
| Channel Gateway | 多渠道入口與訊息正規化（含台語/拼音/OCR） |
| Identity & Tenant Manager | 身分、權限、租戶隔離 |
| Conversation Manager | 對話狀態、上下文、SLA |
| **Hypothesis Engine** | 形成、評分、追蹤、calibrate hypothesis |
| Agent Orchestrator | 決定由哪個 AI 員工或 skill 處理 |
| Reasoning & Cost Router | 根據風險、難度、SLA、成本選擇推理策略 |
| Agent Runtime | Hermes-like 推理、記憶、工具調用 |
| Memory System | 分層記憶、過期、PII、可遷移 |
| Skill Registry | 技能版本、風險、測試、發布、belief-condition trigger |
| Knowledge & RAG Layer | 正式知識、SOP、文件版本、entity-aware retrieval |
| Tool & Workflow Layer | CRM、工單、訂單、通知、派工 |
| **Passive Label Pipeline** | 自動比對真人實際送出 vs AI 建議 |
| Training Sandbox | 專家訓練、模擬、案例標註 |
| Evaluation & Release | 測試、灰度、A/B、回滾、eval freshness audit |
| Observability & Security | 監控、審計、威脅偵測、成本控管 |

### 16.3 容器間通訊協定

`[TBD-W2]` — 待補：每對容器的 sync / async / event 通訊方式、failure mode。

---

## §17 Component View（C4 Level 3）— 七層子系統

> **Reader**：開發團隊 / SRE / 新工程師
> **Decision**：實作各子系統內部
> **Evidence Needed**：每個子系統的 components、interfaces、data contracts

### 17.1 Channel Gateway

**責任**：多渠道入口的訊息正規化。

| Component | 功能 |
| :--- | :--- |
| Channel Adapter（LINE / WA / Web / Email） | 通道協定轉換 |
| Language Normalizer | 台語對照、注音糾錯、長輩錯字 |
| OCR Pipeline | 圖片 → 文字（維修現場拍照常見） |
| Sticker Tagger | 貼圖 → 語義標籤 |
| Author/Owner Validator | 帳號 owner ≠ 訊息 author 的辨識 |
| Original Preserver | 保留原文供 audit |

**關鍵設計（離線/半離線）**：訊息送達確認、圖片優先上傳、失敗明確告知，不靜默。

### 17.2 Conversation Runtime Layer（核心）

**這是 v2 對 v1 最重要的架構新增層**。

#### 17.2.1 為何需要這層

v1 的 skill registry 預設 utterance trigger，會踩到三類典型錯誤：

| 客戶輸入 | 錯誤行為 | 根因 |
| :--- | :--- | :--- |
| 「我想看電子鎖」 | bot 問「您的電子鎖是什麼品牌？」 | 假設 ownership=already_owned 且要先填 slot |
| 「Chatlock」（單詞） | bot 問「您的 Chatlock 是哪個型號？」 | trigger 命中『品牌名 → 保修流程』 |
| 「我還沒買，我是想看」 | bot 流程重來 | 沒有跨輪 belief 更新機制 |

Belief-driven 架構天然避開這三類錯誤，**不需要特例規則**。

#### 17.2.2 Hypothesis Engine

從 utterance + history + entity context 形成 1-3 個 ranked hypothesis（含 `likely_misframe`）。Schema 見 §12.2。

#### 17.2.3 Belief State Manager

維護結構化 belief、每 turn snapshot、寫入 Trace。

#### 17.2.4 Action Decision Policy

| Top hypothesis confidence | 次高 | 觸發條件 | 決策 |
| :--- | :--- | :--- | :--- |
| ≥ 0.75 | < 0.4 | — | COMMIT |
| 0.4 – 0.75 | ≥ 0.3 | — | PROBE |
| < 0.4 | — | — | EXPLORE |
| any | — | 涉及報價、客訴、危險操作 | ESCALATE |
| any | — | cost_sensitivity > 0.7 | 強制 COMMIT 或 ESCALATE，禁用 PROBE/EXPLORE |
| any | — | tool 連續失敗 ≥ 2 次 | ESCALATE |

**Information Gain Probe 啟發式**：
- 兩個 top hypothesis 在 `ownership_status` 上不同 → 直接問 ownership
- 在 `underlying_goal` 上不同 → 用「您最在意 X 還是 Y？」二選一
- 避免問需要客戶有專業知識才能回答的問題

#### 17.2.5 Calibration Engine

讀客戶下一輪反應，更新 belief。Tool 失敗也作為 evidence：

| Tool 結果 | Belief 更新 |
| :--- | :--- |
| 成功且資料一致 | top hypothesis confidence +0.1 |
| 成功但資料矛盾 hypothesis | top hypothesis confidence -0.2，提升次高 |
| 失敗（404 / not found） | 增加 hypothesis「資料不存在」，可能要 ESCALATE |
| 失敗（timeout / 5xx） | 連續 2 次 → ESCALATE，不消耗客戶耐心 |

#### 17.2.6 三層 Meta-Skill Prompt（入 DB）

| 層 | Meta-Skill | 教什麼 | 存放 |
| :--- | :--- | :--- | :--- |
| L1 | Hypothesize | 怎麼從 utterance + 歷史 + entity context 形成 1-3 個 ranked hypothesis | DB `prompt_versions` |
| L2 | Decide | 怎麼從 belief 選 action type；何時 probe、commit | DB `prompt_versions` |
| L3 | Calibrate | 怎麼讀客戶反應；如何更新 belief | DB `prompt_versions` |

業主後台可調整客服行為而不需重新部署。

#### 17.2.7 Skill.trigger = Belief Condition（v2 關鍵決策）

```text
v1: skill.trigger = "客戶提到品牌名"  ← keyword based
v2: skill.trigger = {
      primary_intent: "support",
      ownership_status: "already_owned",
      brand_known: true,
      urgency: ["medium", "high"]
    }  ← belief condition based
```

Orchestrator 根據當前 belief 查 registry，找到 matching belief condition 的 skill。對應 ADR-002。

#### 17.2.8 與 Explicit Classifier 共存

Classifier 在 v2 中**不再是 router，而是 Hypothesize 階段的 evidence 之一**：

```text
User Utterance
  ├──→ [可選] Explicit Classifier ──→ classifier_signal: {intent, conf}
  │                                          ↓
  └──→ Hypothesis Engine ─────────── 把 classifier_signal 作為 evidence 之一
```

Classifier 給快、便宜的初步訊號；Hypothesis Engine 給完整 belief。兩者互補。

### 17.3 Agent Runtime Layer

#### 17.3.1 AgentRuntimeAdapter v1.0

```text
AgentRuntimeAdapter v1.0
- run_turn(context, tools, policies) -> turn_result
- search_memory(query, scope) -> memory_chunks
- propose_skill(trace) -> skill_proposal
- execute_skill(skill_id, input) -> skill_result
- summarize_session(session_id) -> session_summary
- export_state() / import_state()
- get_belief() / update_belief(evidence)  ← v2 新增
```

這層讓 Hermes 可以先上線，但未來仍可替換或並行其他 runtime（OpenAI Agents、LangGraph、Custom）。完整 OpenAPI 見附錄 D。

#### 17.3.2 Hermes Fork-and-Pin Strategy

v1 主張「不要 fork」，但 Hermes 是 0.x，**live track upstream 是生產風險**。v2 修正為：

1. Fork Hermes 到內部 monorepo，pin 特定 commit
2. 對接面用 `AgentRuntimeAdapter` 抽象介面
3. 每季 rebase 一次，rebase 前跑完整 regression test
4. 重大 breaking change 上游時，平行運行新舊版直到驗證 stable
5. 平台層的工具、記憶、技能介面**不可直接耦合 Hermes 內部結構**

對應 ADR-004。

#### 17.3.3 Reasoning & Cost Router

詳見 §34 Cost Architecture。

### 17.4 Memory & Skill Layer

#### 17.4.1 Memory Router

決定一段資訊能不能被記住、被誰使用、何時過期。詳見 §14.2。

#### 17.4.2 Skill Registry（belief-condition trigger）

詳見 §12.3。

#### 17.4.3 Knowledge & RAG Layer（entity-aware retrieval）

`[TBD-W2]` — 待補：entity-aware retrieval 演算法、index 設計、freshness 機制。

### 17.5 Tool & Workflow Layer

#### 17.5.1 Tool Risk Tier L0-L4

| 等級 | 工具例子 | 控制 |
| :--- | :--- | :--- |
| L0 | 查公開 FAQ | 可自動 |
| L1 | 查訂單狀態（單一帳號） | 需身份驗證 |
| L2 | 建工單、改預約 | 可自動，但需 trace + 客戶確認 |
| L3 | 退款、改帳務、取消合約 | 人工批准 |
| L4 | 法律、醫療、重大財務承諾 | 禁止自動決策，轉人工 |

對應 ADR-010。

#### 17.5.2 Human Approval Workflow

`[TBD-W2]` — 待補：L3 操作的 approval queue、timeout、escalation 流程。

### 17.6 Training & Evaluation Layer

#### 17.6.1 Passive Diff Engine（v2 主訊號源）

v1 的 learning loop 假設專家會主動審核。**現實是 9 成客服只想下班，主動標註不可能規模化**。v2 修正：

```text
真人客服送出最終回覆（這是他本來就要做的事）
        ↓
Passive Diff Engine：自動計算 (真人實際送出, AI 建議答案)
        ↓
Diff Classifier：
  ├─ 接近一致（>90% 相似）→ 自動進 positive sample
  ├─ 中度差異 → 進 review queue（high-uncertainty candidate）
  └─ 高度差異 → 進 priority review queue（學習價值最高）
        ↓
Expert Quick Review（30 秒內完成的卡片式介面）
        ↓
Learning Candidate → Skill Proposal → Eval → Release
```

對應 ADR-003。

#### 17.6.2 Passive Label 品質保證

直接用真人回覆當 ground truth 會把真人錯誤一起學進來。對策：

| 機制 | 作用 |
| :--- | :--- |
| 多位真人 consensus | 三位以上一致才當高信心 label |
| 客戶反應 signal | 是否再追問？是否轉人工？是否關閉對話？implicit reward |
| 抽樣專家審核 + 校準 | 每月抽 5% passive label 給專家確認 |
| Outlier 排除 | 偏離團隊主流的真人回覆標 flag，不直接當 positive |

#### 17.6.3 雙迴路設計

```text
Production Serving Loop（用已發布版本）
使用者訊息 → Hypothesis Engine → 已發布版本的 K/M/S → 回覆或執行任務

Learning Loop（與 Serving Loop 並行但隔離）
對話 trace → 清洗與隔離 → Passive Diff → learning candidate → 審核與評估 → 版本化發布
```

#### 17.6.4 Evaluation Harness（含 Freshness Audit）

| Dataset | 用途 |
| :--- | :--- |
| Golden Answers | 測試標準回覆 |
| Edge Cases | 測試例外情境 |
| Safety Set | 測試高風險拒答 |
| Prompt Injection Set | 測試攻擊防線 |
| Tool Simulation Set | 測試工具操作 |
| Tenant Regression Set | 防止客戶規則被破壞 |
| **Distribution Audit Set** | **與線上 distribution 對比、檢測 drift**（v2） |

#### 17.6.5 Canary Release + Rollback

詳見 §37 AI Behavior CI/CD。

### 17.7 Service Governance Layer

#### 17.7.1 Tenant Manager

`[TBD-W2]` — 待補：tenant lifecycle（create / upgrade / suspend / delete）、quota、billing 對接。

#### 17.7.2 Brand Policy Manager

`[TBD-W2]` — 待補：品牌話術、用詞禁忌、tone 設定的 schema 與管理介面。

#### 17.7.3 Escalation Policy Manager

`[TBD-W2]` — 待補：escalation rules、SLA breach、人工接手交接流程。

---

## §18 Multi-Agent Orchestration

> **Reader**：Architect / 開發團隊
> **Decision**：AI Employee 抽象的內部組合
> **Evidence Needed**：Sub-agent 清單與職責、編排策略

### 18.1 AI Employee 抽象

產品上，企業客戶看到的是「一位 AI 員工」。系統上：

```text
AI Employee
  =
Customer Service Harness
  + Agent Orchestrator
  + Hypothesis Engine
  + Runtime Adapter
  + Memory System
  + Knowledge Layer
  + Skill Registry
  + Tool & Workflow Layer
  + Governance Layer
  + Evaluation & Release System
```

即：

```text
一套被包裝成員工身份、具備權限邊界、可被派工、可被審計、可被複訓的作業系統單元。
```

### 18.2 Sub-Agent 清單

| Sub-agent | 職責 |
| :--- | :--- |
| Intent Agent | 判斷使用者目的、任務類型、緊急程度（作為 Hypothesis Engine 的 evidence） |
| Policy Agent | 檢查品牌規則、風險、可否回答、是否轉人工 |
| Retrieval Agent | 查詢知識庫、歷史案例、SOP、相似對話 |
| Skill Agent | 依 belief condition 選擇可執行的 skill 或 workflow |
| Tool Agent | 呼叫 CRM、訂單、工單、通知、派工系統 |
| Safety Agent | 檢查輸入攻擊、輸出風險、敏感資料 |
| Learning Agent | 從對話 trace 與 Passive Diff 產生 learning candidate |
| Evaluation Agent | 對新 knowledge、memory、skill 做測試與回歸 |

### 18.3 編排策略

外部呈現要簡單：

```text
這是某企業訓練出的 AI 客服員工。
```

內部實作要清楚：

```text
這是 harness + orchestrator + Hypothesis Engine + 多個 sub-agent + governance + tool chain 的組合。
```

這個拆法讓平台可以更換底層模型、替換 Hermes runtime、增加專門 sub-agent、限制工具權限，而不破壞「AI 員工」這個產品抽象。

---

## §19 Sequence Diagrams

> **Reader**：開發團隊 / SRE / 新工程師
> **Decision**：理解關鍵流程
> **Evidence Needed**：4+ 條關鍵 sequence 的逐步圖

### 19.1 標準對話流程（13 步驟）

```text
1.  客戶送出訊息
2.  Channel Gateway 正規化（台語/拼音糾錯、OCR、貼圖標籤化）
3.  Identity & Tenant Manager 判斷租戶、使用者、權限、author 是否為 owner
4.  Conversation Manager 取得對話狀態與既有 belief
5.  Governance Layer 檢查安全、品牌、風險、轉人工規則
6.  Hypothesis Engine：
    6.1 形成 1-3 個 ranked hypothesis（含 likely_misframe）
    6.2 評估信心、決定 action type
    6.3 若 ESCALATE → 跳到 10
7.  Reasoning & Cost Router：依風險、複雜度、SLA、預算選推理策略
8.  Orchestrator 依 belief condition 選 skill / workflow
9.  Agent Runtime 查記憶、查知識（entity-aware RAG）、推理下一步
10. Tool Layer 執行低風險操作或提出高風險授權請求
11. 回覆送出或交給真人審核
12. 客戶下一輪訊息進來 → Hypothesis Engine 執行 Calibration
13. 全程寫入 trace、audit、cost meter、learning candidate
```

完整 sequence 圖 `[TBD-W2]`。

### 19.2 Tool 失敗 → Escalation 流程

`[TBD-W2]` — 待補：tool 連續失敗 2 次 → belief 更新 → ESCALATE → 人工接手交接的完整 sequence。

### 19.3 Passive Label → Skill Release 流程

完整管線：

```text
多用戶聊天
  ↓
Conversation Stream / Trace Log
  ↓
Tenant ID / User ID / Channel ID 標記
  ↓
PII Redaction / Sensitive Data Filter
  ↓
Prompt Injection / Abuse Detection
  ↓
Passive Diff Engine（v2）
  ↓
Learning Candidate Extractor
  ↓
Case Clustering / Deduplication / Error Attribution
  ↓
Candidate Router
  ├─ Knowledge Proposal
  ├─ Memory Proposal
  └─ Skill Proposal
  ↓
Expert Quick Review / Automated Evaluation
  ↓
Sandbox Regression
  ↓
Canary Release
  ↓
正式版本
```

解決三個問題：

| 問題 | 若直接學習會怎樣 | 正確防線 |
| :--- | :--- | :--- |
| 客戶亂教 AI | 錯誤話術被吸收 | learning candidate 需審核 |
| A tenant 經驗污染 B tenant | 規則與資料混用 | tenant scope 與 memory router |
| prompt injection 污染長期行為 | 攻擊內容變成規則 | injection filter 與 safety evaluation |

Production runtime 只能讀「已發布版本」（Published K/M/S/Policies）；未發布只能在候選區（Candidate K/M/S、Incident Queue）。

### 19.4 Memory Drift → Snapshot Rollback 流程

`[TBD-W2]` — 待補：drift score 計算 → 閾值超過 → human review queue → snapshot rollback → audit 的完整 sequence。

---

# Part V — 整合架構（Integration Architecture）

---

## §20 Service Catalog & API Inventory

> **Reader**：Integration Architect / 客戶開發團隊 / 整合夥伴
> **Decision**：可整合的 API 與 schema
> **Evidence Needed**：完整 API 清單 + OpenAPI spec

### 20.1 公開 API（給客戶整合）

`[TBD-W2]` — 待補完整 catalog。預計分類：

| 類別 | 範例 |
| :--- | :--- |
| Conversation API | start_conversation / send_message / get_status |
| Knowledge API | upload_document / version_management / search |
| Skill API | list / install / configure / disable |
| Memory API | get / forget（right-to-be-forgotten） |
| Tenant API | provision / configure / billing |
| Webhook API | conversation events / skill release events |
| Analytics API | metrics export |

### 20.2 內部 API（layer 間）

`[TBD-W2]` — 待補完整 catalog。

### 20.3 AgentRuntimeAdapter 介面規格

詳細 OpenAPI 規格見附錄 D。

---

## §21 Integration Patterns

> **Reader**：Integration Architect / 開發團隊
> **Decision**：每個整合場景的最佳 pattern
> **Evidence Needed**：sync / async / event / batch 範例與決策樹

`[TBD-W2]` — 待補：

| Pattern | 適用場景 |
| :--- | :--- |
| Sync Request-Response | 即時客戶對話、低延遲 tool call |
| Async Event-Driven（Pub-Sub） | Passive Diff Pipeline、Skill Release event |
| Webhook / Callback | 與 LINE OA、客戶 CRM 的事件通知 |
| Batch / Stream Processing | 對話 trace 清洗、月度報表 |
| MCP（Model Context Protocol） | 標準工具呼叫、跨 runtime 相容 |

---

## §22 External Integrations

> **Reader**：Integration / Business Development
> **Decision**：上線需要哪些第三方整合
> **Evidence Needed**：每個整合的協定、認證、SLA

### 22.1 客戶系統

`[TBD-W2]` — 待補：CRM（Salesforce / HubSpot）、ERP、POS、Ticket（Zendesk / Freshdesk）、Order、會員系統的接入規格。

### 22.2 通訊渠道

| Channel | 協定 | 特化需求 |
| :--- | :--- | :--- |
| LINE OA | Messaging API | 台灣藍領場景必備、貼圖、Flex Message |
| WhatsApp Business | Cloud API | 跨境客戶 |
| Web Chat | WebSocket / SSE | Embedded 部署 |
| Email | IMAP / SMTP | 非同步處理 |

### 22.3 LLM Providers

| Provider | 模型 | 用途 |
| :--- | :--- | :--- |
| Anthropic | Haiku 4.5 / Sonnet 4.6 / Opus 4.6 | Primary（依 Cost Router） |
| OpenAI | GPT-4 / GPT-4o | Backup / 對比 eval |
| Local（Llama / Mistral） | 自部署 | Regulated tenant |

對應 ADR-004 Fork-and-Pin。

### 22.4 監控與分析

`[TBD-W2]` — 待補：Datadog / Grafana / Sentry / OpenTelemetry 接入。

---

# Part VI — 技術架構（Technology Architecture）

---

## §23 Technology Stack

> **Reader**：CTO / 工程主管 / 新工程師
> **Decision**：技術選型 rationale
> **Evidence Needed**：每層選型 + 為什麼

`[TBD-W2]` — 待補完整選型表。原則：

| 層 | 候選 | 偏好 |
| :--- | :--- | :--- |
| 語言 | Python（AI/runtime）+ TypeScript（前端 / API gateway） | Python 主、TS 輔 |
| Runtime | FastAPI / Starlette | FastAPI |
| Worker | Celery / Arq / Temporal | Temporal（workflow） |
| DB | PostgreSQL 16+ | RLS、JSONB、pgvector |
| Cache / Queue | Redis 7+ | Stream / Pub-Sub |
| Container | Docker + Kubernetes | k8s production |
| CI/CD | GitHub Actions + Argo | GitOps |

---

## §24 Deployment View

> **Reader**：SRE / DevOps / 客戶 IT
> **Decision**：部署拓樸、環境策略、多 region 設計
> **Evidence Needed**：邏輯拓樸圖、環境表、HA 設計

### 24.1 核心原則：Stateless Compute + Stateful Storage

這一節回答兩個常見的 mental model 錯誤：

> **錯誤 1**：「LLM API 就是平台」——把白皮書的能力誤以為全部能靠 LLM 推理 + Anthropic API 解決。
>
> **錯誤 2**：「每個客戶要個性化 → 每個客戶一個 agent process」——把「狀態（state）」跟「執行單元（process）」綁在一起。

#### 24.1.1 LLM 能力 vs 平台工程的分界

對應 §17 七層子系統的工程量分布。平台能力大致可分三類：

| 類別 | 比例 | 例子 | 主要落點 |
| :--- | :---: | :--- | :--- |
| **LLM 原生可解** | ~30% | Hypothesize、Decide、Calibrate、語意分類、台語/拼音 normalization、OCR、misframe 偵測、skill execution loop | §17.2 / §17.3 |
| **半工程半 LLM** | ~15% | Passive Diff、Memory drift scoring、PII detection | §17.6 / §14.3 / §14.4 |
| **純工程** | ~55% | Multi-tenant 隔離、Skill registry 版本回滾、Audit trace、Tool 整合（CRM/ERP/工單）、Authentication、Cost meter、Eval freshness、Channel gateway、垂直法規 gating | §17.1 / §17.4 / §17.5 / §17.7 / §14 / §34 |

**含義**：LLM 變強只縮短了 30% 的時間；剩下 70% 的工程不會因為 GPT-5 出來就自動寫好。

```text
Anthropic API 給你的是 inference endpoint，
給不了你 multi-tenant、audit、deployment、cost meter。
```

#### 24.1.2 設計原則

```text
Compute（worker process）→ Stateless
State（conversation / memory / skill / belief）→ Stateful，存於 DB
個性化 → 來自 per-request 從 DB 載入的 context，不來自 process 隔離
```

這跟 ChatGPT 服務 1 億 user 的設計同構——不為每個 user 起一個 process，而是**所有 user 共用同一個 stateless inference pool，每個 request 帶入該 user 的 context**。

### 24.2 邏輯部署拓樸

對應 §16.1 七層架構與 §16.2 容器級組件清單。完整 sequence 請見 §19 Sequence Diagrams。

```text
[LINE webhook / WhatsApp / Web Chat] ........... Layer 7（§17.1 Channel Gateway）
     │
     ▼
[API Gateway]
  - 驗證訊息簽章
  - 解析 tenant_id、user_id
  - Rate limit by tenant
     │
     ▼
[Conversation Manager]（Stateful Storage / Stateless Compute）... Layer 5/6
  - 從 DB 撈 conversation_state（含 belief snapshot，§12.2）
  - 從 DB 撈 tenant_config（品牌、policy、可用 skill 清單，§13）
  - 從 DB 撈 user_memory（RAG retrieve，§17.4）
  - 組裝 inference request payload
     │
     ▼
[Hypothesis Engine Worker Pool]（stateless, 水平擴展）...... §17.2.2
  - 呼叫 Anthropic API（含 system prompt + belief schema + tenant policy）
  - 輸出新 belief + action decision
     │
     ▼
[Reasoning & Cost Router] .................................. §34.2
  - 依 belief 風險、複雜度、SLA、預算選 model tier 與推理策略
  - 路由到 rule / RAG / Haiku / Sonnet / Opus / multi-agent critique / handoff
     │
     ▼
[Skill Executor Worker Pool]（stateless, 水平擴展）......... §17.4
  - 依 belief condition 從 Skill Registry 選 skill
  - 執行 tool calling（CRM / 工單 / 通知，§17.5）
  - 產出 reply
     │
     ▼
[Conversation Manager]
  - 寫回 conversation_state、belief、trace、cost meter
  - 推 Passive Diff job 到背景 queue
  - 回應推回 Channel
     │
     ▼
[背景 Pipeline]（asynchronous, decoupled）... Layer 2（§17.6）
  - Passive Diff Engine
  - Learning Candidate Extractor
  - Eval Freshness Audit
  - Memory Drift Detector（§14.3）
```

關鍵屬性：

| 屬性 | 說明 |
| :--- | :--- |
| Worker pool 服務範圍 | 所有 tenant、所有 user 共用 |
| 個性化來源 | DB 載入的 per-request context |
| 擴容方式 | 加 worker 數，與 tenant 數無關 |
| 背景 Pipeline | 與線上 serving 解耦，不阻塞 SLA |

### 24.3 個性化注入維度

對應 §12 Logical Data Model 與 §13 Physical Data Architecture。所有維度都以 `tenant_id` 為頂層索引（§14.1 Pace-Layered Governance）。

| 個性化維度 | 來源 | 注入時機 |
| :--- | :--- | :--- |
| 品牌口吻 | `tenant_config.brand_voice_policy` | 每 request system prompt |
| 可用工具 | `tenant_config.tool_permissions` | 每 request tool list |
| SOP 流程 | `skill_registry` filtered by `tenant_id` + `belief_condition` | 每 request skill list |
| 客戶歷史 | `user_memory` by `user_id`（RAG retrieve） | 每 request context chunks |
| 對話 state | `conversation_state` by `conversation_id` | 每 request belief snapshot |
| 客戶偏好 | `user_profile`（語氣、稱呼、語言） | 每 request system prompt |
| 法規分層 | `domain_config` by tenant 所屬產業 | 每 request policy block |

全部都是 **per-request context injection**，沒有任何一項需要 per-tenant process。

### 24.4 為何「per-tenant process」是反模式

| 問題 | 結果 |
| :--- | :--- |
| 每 process 200MB-1GB RAM | 1000 tenant = 200GB-1TB RAM |
| Cold start 延遲 | 破壞 LINE webhook SLA |
| 跨 process 共享 skill registry / model client 困難 | 每個 tenant 重複載入相同 base policy |
| 部署、監控、擴縮容地獄 | 加 tenant = 加 deployment unit |
| Hermes `~/.hermes/` 是 single-user 檔案系統 | 沒有 tenant 隔離維度，必須 fork |

**結論：Process 數量應由 QPS 決定，與 tenant / user 數量解耦。**

### 24.5 Multi-Tenant DB Schema 原則

對應 §13 Physical Data Architecture 與 §14 Data Governance。

| 原則 | 說明 |
| :--- | :--- |
| `tenant_id` 為所有業務表的頂層索引 | 任何查詢必帶 tenant_id |
| Row-level Security 或 query-level filter 強制隔離 | 不可信任 application layer 自律 |
| Memory / Skill / Knowledge 都 namespaced by tenant_id | 跨 tenant 共享只在明確同意 + 匿名化後（§14.6） |
| Audit log 全程記 tenant_id | 對應 §32 Operability & Observability |
| Vector DB 用 metadata filter by tenant_id | 而非每 tenant 一個 collection（後者擴容困難） |

### 24.6 Session Affinity 該不該做

| 場景 | 是否需要 affinity |
| :--- | :--- |
| 一般對話 serving | 不需要——session state 從 DB 載入，任何 worker 都能處理 |
| 熱資料快取（同一對話短時間多輪） | 可選——加 in-memory cache 可省 DB round-trip |
| Long-running streaming response | 需要——streaming 期間綁定 worker |
| 多步 tool calling 中途 | 不需要——每步寫回 DB |

**預設不做 session affinity**。只在觀測到熱資料 cache miss 太多時才加 sticky routing，且必須有 fallback。

### 24.7 Hermes / Runtime Adapter 部署位置

如果採用 Hermes（透過 §20.3 `AgentRuntimeAdapter` 介面規格），它只在 worker 內部以**函式呼叫**形式存在，不是常駐 process：

```text
Worker process（stateless）
  ├── 接收 request payload（含 tenant_id、user_id、belief、context）
  ├── 呼叫 HermesAdapter.run_turn(...) ← Hermes 的 agent loop 在這
  │     └── 內部打 Anthropic API
  └── 回傳結果 → Conversation Manager 寫回 DB
```

**Hermes 的 `~/.hermes/sessions/`、`~/.hermes/memories/`、`~/.hermes/skills/` 完全不用**。改由平台的 DB / vector store 提供同等資料，透過 adapter 注入。這樣：

- Hermes 0.x 上游 breaking change 影響範圍可控
- Multi-tenant 隔離不靠 Hermes，靠平台 DB
- 可換成 OpenAI Agents、LangGraph、Custom Runtime 而不動 storage

### 24.8 環境策略

| 環境 | 用途 |
| :--- | :--- |
| Dev | 開發 |
| Staging | 整合測試 |
| Canary | 5% 流量灰度 |
| Production | 全流量 |
| Sandbox（per-tenant） | 客戶訓練專用 |

### 24.9 容量規劃（粗估）

成本基數來自 §34.4 Token Economics 拆解（Sonnet 4.6、優化後單輪 ~$0.018）、平均 8 turn / conversation：

| 規模 | Worker pool | DB | 月度推理成本（活躍對話 / 月）|
| :--- | :--- | :--- | :--- |
| 10 tenant, 10k conv/月 | 2-4 worker | 1 Postgres + 1 vector | ~$1,440 |
| 50 tenant, 100k conv/月 | 8-16 worker | Postgres replica + vector cluster | ~$14,400 |
| 200 tenant, 500k conv/月 | 30-60 worker | Postgres HA + vector cluster + cache | ~$72,000 |

注意：worker 數量隨 QPS 線性增長，但 **與 tenant 數不直接相關**。10 tenant vs 200 tenant 的差異主要是 DB 規模與背景 pipeline 量，不是 worker pool 大小。

### 24.10 Multi-Region Deployment

`[TBD-W2]` — 對應 §14.7 資料在地化。

設計重點：
- Tenant 綁定 home region（資料主權）
- Cross-region 不複製 raw conversation log
- 僅 anonymized skill / eval dataset 可跨區共享（明確同意後）

### 24.11 高可用設計

`[TBD-W2]` — 對應 §31 Reliability。

設計重點：
- Worker pool stateless → 任一 instance 失敗不影響資料一致性
- DB 走 primary-replica + automated failover
- 背景 Pipeline 可重跑（idempotent）
- Anthropic API 失敗 fallback：降級到 cached response 或自動轉人工

---

## §25 Reference Architectures

> **Reader**：客戶 EA / 採購評估
> **Decision**：部署選項與適用情境
> **Evidence Needed**：3 種部署架構對比

`[TBD-W2]` — 待補：

| 模式 | 適用 | 優勢 | 限制 |
| :--- | :--- | :--- | :--- |
| Single-Tenant Reference | 小型客戶 / PoC | 簡單 | 成本高 |
| Multi-Tenant Shared | 中型客戶 | 成本低 | 隔離靠軟體 |
| Enterprise Dedicated | 大型 / Regulated | 強隔離 | 部署複雜 |

---

# Part VII — 安全與合規架構（Security & Compliance）

---

## §26 Threat Model

> **Reader**：CISO / Security Team / Architect
> **Decision**：威脅清單與優先級
> **Evidence Needed**：STRIDE / DREAD / LLM-specific 三套

### 26.1 通用風險框架

依據 NIST GenAI Profile 2024-07-26 與 OWASP Top 10 for LLM Applications：

| 風險 | 描述 | 防線（見 §27） |
| :--- | :--- | :--- |
| Prompt Injection | 客戶或外部文件誘導 AI 忽略規則 | 輸入隔離、工具權限、指令分層、攻擊測試 |
| Sensitive Data Disclosure | 洩漏個資、訂單、內部規則 | PII redaction、租戶隔離、輸出掃描 |
| Excessive Agency | AI 可做超過職責的動作 | 最小權限、人工批准、工具風險分級 |
| Hallucination | 編造政策、費用、承諾 | RAG grounding、信心門檻、轉人工 |
| Unbounded Consumption | 成本或資源失控 | Rate limit、budget guardrail、queue control |
| **Memory Poisoning**（v2） | 長期記憶被污染 | Drift detection、snapshot rollback、cross-session 治理 |
| **Tool Result Tampering**（v2） | 工具回傳被偽造 | Tool output schema validation |

### 26.2 STRIDE 分析

`[TBD-W2]` — 待補完整 STRIDE × LLM 場景對應。

### 26.3 DREAD 評分

`[TBD-W2]` — 待補。

---

## §27 Security Controls

> **Reader**：CISO / Security Team
> **Decision**：控制完整性、實作優先級
> **Evidence Needed**：每個 control 的實作位置、驗證方式

### 27.1 Identity & Access Management

`[TBD-W2]` — 待補：SSO、RBAC、MFA、API Key 管理。

### 27.2 Tenant Isolation

- DB row-level security（`tenant_id` 強制過濾）
- Vector DB per-tenant namespace
- Memory Router 預設不跨 tenant
- API Gateway tenant context propagation

### 27.3 PII Redaction Pipeline

詳見 §14.4。

### 27.4 Prompt Injection Defense

`[TBD-W2]` — 待補：input sanitization、指令分層、attack test set、red team 流程。

### 27.5 Audit Logging（含 belief snapshot）

詳見 §12.5。

---

## §28 Compliance Matrix

> **Reader**：法遵 / 稽核 / 客戶 CCO
> **Decision**：對應法規的證據在哪
> **Evidence Needed**：需求 ↔ 控制 ↔ 證據 三向對應表

### 28.1 通用合規

`[TBD-W2]` — 待補完整 matrix。涵蓋：
- NIST GenAI Profile 2024-07-26
- ISO 27001
- GDPR / 台灣個資法
- SOC 2 Type II

### 28.2 垂直法規對應表

| 垂直 | 適用法規 | 核心要求 | 對 AI 客服影響 |
| :--- | :--- | :--- | :--- |
| 電商售後 | 消費者保護法、個資法 | 七天鑑賞期、退款規範 | 自動承諾退款邊界、退款流程必須 audit trail |
| 維修派工 | 消保法、商品標示法 | 保固期、維修紀錄 | 工單操作必須可追溯，技師指派紀錄保留 |
| 餐飲訂位 | 食安法（間接） | 過敏資訊揭露 | 涉及食材成分提問轉人工 |
| SaaS 客服 | 個資法、跨境傳輸 | 資料在地化 | tenant memory 不可跨地區複製 |
| 物業客服 | 公寓大廈管理條例 | 公共議題決議流程 | 涉及住戶投票、財務決策必轉人工 |
| 保險理賠 | 保險法、金管會規範 | 個案核保不可自動化 | 全部需轉人工 |
| **跨垂直共通** | **EU AI Act Article 50** | **透明告知與 AI 互動** | **首訊必須告知「您正在與 AI 客服對話」** |

### 28.3 EU AI Act Article 50 透明告知

使用者直接與 AI 系統互動時，需被告知正在與 AI 系統互動。即使不在歐盟市場，這也是企業信任的基本設計。

```text
透明告知：使用者知道這是 AI 協助或 AI 客服。
責任邊界：高風險事項可轉人工。
行為可追溯：每次回覆、工具調用與決策都有 trace。
```

### 28.4 控制 ↔ 需求 ↔ 證據三向對應表

完整版見附錄 F。

---

## §29 Privacy by Design

> **Reader**：DPO / 法遵 / 隱私倡議者
> **Decision**：隱私設計成熟度
> **Evidence Needed**：資料最小化、同意管理、Right-to-be-Forgotten 流程

`[TBD-W2]` — 待補。

---

# Part VIII — 品質屬性（Quality Attributes / NFRs）

---

## §30 Performance & Scalability

> **Reader**：SRE / Architect / 採購評估
> **Decision**：能否承載目標流量
> **Evidence Needed**：SLO 量化（P50/P95/P99）、scaling test 結果

`[TBD-W2]` — 待補完整量化。原則：

| 指標 | 目標 |
| :--- | :--- |
| Latency P50 | < 2s（單輪對話） |
| Latency P95 | < 5s |
| Latency P99 | < 10s |
| Throughput | TBD（依 tenant 規模） |
| Concurrent Conversations | TBD |

---

## §31 Reliability & Availability

`[TBD-W2]` — 待補。原則：

| 指標 | 目標 |
| :--- | :--- |
| SLA | 99.9% |
| RTO | < 1 hour |
| RPO | < 5 minutes |

---

## §32 Operability & Observability

> **Reader**：SRE / DevOps / 平台運營
> **Decision**：監控完備性、incident response 能力
> **Evidence Needed**：metrics / tracing / alerting policy

### 32.1 Logging Strategy

每 turn 必含：utterance / belief / action / tool calls / response / cost / risk flags。

### 32.2 Metrics（含 v2 新增）

| 指標 | 用途 |
| :--- | :--- |
| Cost per Turn | 單輪對話成本 |
| Cost per Resolved Task | 單個已解決任務成本 |
| Model Mix | 各模型使用比例 |
| Escalation Cost | 轉人工與高階模型成本 |
| Quality per Cost | 每單位成本帶來的品質 |
| Router Error Rate | 路由錯誤率 |
| Automation Resolution Rate | 自動解決率 |
| Human Escalation Precision | 轉人工是否準確 |
| **Human Escalation Success Rate**（v2） | 轉人工後真人也解決得了嗎 |
| Expert Approval Rate | 專家接受率 |
| **Passive Label Quality Score**（v2） | 真人/AI diff 一致性趨勢 |
| Regression Pass Rate | 發布穩定性 |
| **Eval Freshness Score**（v2） | eval set 與線上 distribution 距離 |
| Tenant Expansion Rate | 客戶內擴張 |

### 32.3 Tracing

`[TBD-W2]` — 待補：OpenTelemetry / W3C Trace Context 接入。

### 32.4 Alerting Policy

`[TBD-W2]`

### 32.5 SRE Runbook

`[TBD-W2]`

---

## §33 Maintainability & Evolvability

`[TBD-W2]` — 待補：API / Skill / Knowledge / Memory 版本化、Backward compat、Deprecation policy。

---

## §34 Cost Architecture

> **Reader**：CFO / 採購評估 / 平台運營
> **Decision**：成本可控性與毛利模型
> **Evidence Needed**：Cost model 完整、Router 設計、優化槓桿

### 34.1 為什麼成本管理是商業模式核心

```text
Cost per Resolved Task
完成一個受治理服務任務的總成本
```

包含：

| 成本項 | 說明 |
| :--- | :--- |
| Model Cost | 小、中、高階模型與 multi-agent critique 的推理成本 |
| Retrieval Cost | 向量搜尋、文件檢索、session search |
| Tool Cost | CRM、工單、訂單、通知、外部 API |
| Human Review Cost | 專家審核、人工轉接、例外處理 |
| Evaluation Cost | sandbox、regression、safety test |
| Failure Cost | 錯誤回覆、客訴、退款、品牌損害 |

### 34.2 Reasoning & Cost Router

核心原則：

```text
不是每個問題都需要最強模型。
不是每個問題都適合最便宜模型。
正確策略是：用符合風險要求的最低足夠推理成本完成任務。
```

路由流程：

```text
User Message
  ↓
Hypothesis Engine（單層 LLM call 取得 belief）
  ↓
Intent / Risk / Complexity Classifier（基於 belief）
  ↓
Reasoning & Cost Router
  ├─ Rule-based flow
  ├─ RAG answer
  ├─ Small model（Haiku）
  ├─ Medium model（Sonnet）
  ├─ Large model（Opus）
  ├─ Multi-agent critique
  ├─ Tool workflow
  └─ Human handoff
```

### 34.3 推理策略對應

| 問題類型 | 推理策略 | 成本策略 | 風險控制 |
| :--- | :--- | :--- | :--- |
| 基礎 FAQ | RAG + 小模型摘要 | 低成本 | 引用正式知識來源 |
| 查訂單狀態 | 工具調用 + 模板回覆 | 低成本 | 身份驗證、trace |
| 補件提醒 | SOP skill + 小模型改寫 | 低成本 | 固定流程與欄位檢查 |
| 退款資格判斷 | Policy check + 中模型 + skill | 中成本 | 規則引用、人工門檻 |
| 客訴升級 | 情緒判斷 + 中高階模型 + handoff policy | 中高成本 | 轉人工策略 |
| 新型複雜問題 | 高階模型 + retrieval + critique | 高成本 | expert review 或 shadow mode |
| 法律、醫療、高額賠償 | 不自動決策 | 控制風險成本 | 轉人工 |

### 34.4 Token Economics 拆解

以 Sonnet 4.6（$3/M input、$15/M output）估算 hypothesis-driven 單輪成本：

```text
Per-turn cost =
  Hypothesize LLM call   (input ~2k, output ~500)
+ Decide LLM call        (input ~1.5k, output ~300)
+ Calibrate LLM call     (input ~1.5k, output ~300)
+ Skill execution LLM call (input ~3k, output ~500)
+ RAG retrieval cost
+ Tool call cost
+ Belief state storage / retrieval
```

- 三層 meta-skill：input ~5k × $3/M = $0.015，output ~1.1k × $15/M = $0.0165
- Skill exec：input ~3k × $3/M = $0.009，output ~0.5k × $15/M = $0.0075
- **單輪總成本約 $0.048**
- 50 turn 對話約 **$2.4 USD**

### 34.5 成本優化槓桿

| 槓桿 | 預期節省 | 實作成本 |
| :--- | :--- | :--- |
| **Prompt caching**（system prompt + skill registry 快取） | 60-70% | 低 |
| **Belief diff**（不傳整個 state） | 20-30% | 中 |
| **Classifier as precheck**（Haiku 4.5 做 explicit classifier） | 30-40% | 中 |
| **Tool result caching** | 10-20% | 低 |
| **Memory pruning**（限制 context 長度） | 15-25% | 中 |
| **Model tier routing**（簡單問題 Haiku、複雜 Sonnet/Opus） | 40-60% | 高 |

優化後**單輪成本目標 $0.015-0.020**，50 turn 對話 $0.75-1.00。

### 34.6 Per-tenant Budget Guardrail

- 每個 tenant、每個 conversation 都要有即時 cost meter
- 月度 budget guardrail（超出自動降級 model tier 或轉人工）

---

## §35 Quality Attribute Scenarios（ATAM）

> **Reader**：Architect / Quality Reviewer
> **Decision**：架構評估通過
> **Evidence Needed**：15+ 場景，每場景含 Source / Stimulus / Artifact / Environment / Response / Response Measure

`[TBD-W3]` — 待補完整 15+ 場景集，存放於附錄 G。

---

# Part IX — 治理與運營（Governance & Operations）

---

## §36 Architecture Governance

> **Reader**：CTO / 工程主管 / 新加入 Architect
> **Decision**：架構決策流程
> **Evidence Needed**：ADR 模板、ARB 流程、例外申請

`[TBD-W2]` — 待補：ADR 流程、ARB（Architecture Review Board）、例外申請、標準清單。

---

## §37 AI Behavior CI/CD

> **Reader**：開發團隊 / 資料科學家 / 平台運營
> **Decision**：行為變更的發布流程
> **Evidence Needed**：完整 pipeline、回滾條件、freshness 機制

### 37.1 發布管線

每個 skill 或 policy 更新都應經過：

```text
Diff → Unit Eval → Regression Eval → Safety Eval →
Tenant-specific Eval → Canary Release (5%) → Monitoring →
Full Release or Rollback
```

**這不是工程潔癖，而是客服產品的責任邊界。**

### 37.2 Eval Freshness Audit

對應 §17.6.4 Distribution Audit Set。

### 37.3 Memory Drift Detection

對應 §14.3。

### 37.4 Skill Deprecation Policy

每季淘汰使用率 <1% 的 skill；trigger 衝突自動 flag。

---

## §38 Operations Model

> **Reader**：平台運營 / SRE / 客服中心 (運營)
> **Decision**：誰做什麼
> **Evidence Needed**：RACI、Incident response、Change management

`[TBD-W2]` — 待補：
- RACI（Build / Run / Train / Audit）
- Incident Response（含 AI-specific incidents）
- Change Management
- Support Tier

---

## §39 Capability Maturity Model

> **Reader**：客戶 / 業務 / 客戶成功
> **Decision**：客戶處於哪一級、怎麼升級
> **Evidence Needed**：5 級定義 + 升級判定指標

### 39.1 五級成熟度

```text
Level 1：AI 客服助理（Copilot）
   ↓
Level 2：AI 實習客服（Shadow Mode）
   ↓
Level 3：AI 初階客服（低風險自動化）
   ↓
Level 4：AI 熟練客服（多步任務 + 人工授權節點）
   ↓
Level 5：AI 藍領員工平台（多租戶、多產業）
   ↓
[生態系階段：垂直服務業 Agent 生態系]
```

### 39.2 各階段成功指標

| 階段 | 主要指標 | 目標 |
| :--- | :--- | :--- |
| Copilot | 建議採用率、節省時間 | >40% 採用，每則 -30s |
| Shadow | 與真人一致率、轉人工準確率 | >70% 一致，escalation precision >85% |
| 低風險自動化 | 自動解決率、錯誤操作率 | >40% 解決，錯誤 <0.5% |
| 熟練 | 多步任務完成率、skill reuse | >60% 完成，skill reuse >50% |
| 平台 | Tenant 數、ARR | >50 tenant |
| 生態系 | Vertical pack 數、partner 數 | 跨垂直跨域 |

第五階段公司不再只是客服軟體，而是：

```text
AI Service Workforce Infrastructure
```

---

# Part X — 實施與遷移（Implementation & Migration）

---

## §40 MVP Definition

> **Reader**：產品 / 工程 / Founder
> **Decision**：Phase 1 範圍與硬 gate
> **Evidence Needed**：MVP 必做 / 不做清單、Phase 1 七工件交付

### 40.1 MVP 不應做的

| 不建議 | 原因 |
| :--- | :--- |
| 完全自動客服 | 風險高、資料不足 |
| 全渠道整合 | scope 失控 |
| 跨產業通用平台 | 無垂直優勢 |
| 自動改 SOP | 企業不會信任 |
| 複雜 agent marketplace | 還沒有核心供給 |
| **要求專家主動標註為主訊號** | 人因不成立 |
| **直接用 utterance trigger 寫 skill** | 與 hypothesis-driven 衝突 |

### 40.2 MVP 應該做的

```text
Expert-trained AI Customer Service Copilot
on Belief-Driven Runtime over Vertical Entity Model
```

### 40.3 Phase 1 硬 gate（動 code 前必須完成）

1. 選定 wedge（建議：電子鎖維修派工）
2. 交付 Entity Model 七工件（§9.3 + 附錄 B）
3. 設計初版 Belief Schema（融合通用維度 + 垂直擴充）
4. 設計初版 Passive Label Pipeline（diff engine + review UI）
5. 寫 ADR-001 至 ADR-010（§47）

### 40.4 Phase 1 MVP 核心功能

| 功能 | 說明 |
| :--- | :--- |
| SOP / FAQ / 案例匯入 | 建立初始知識，**綁定 entity model** |
| Hypothesize（單層 LLM call） | 形成 1-3 個 hypothesis，輸出結構化 belief |
| 客服建議答案（COMMIT 動作） | AI 先輔助真人，**不直接送出** |
| Passive Diff Engine | 自動比對真人實際送出 vs AI 建議 |
| Quick Review Card（30 秒可完成） | 給 high-uncertainty diff 看的卡片式 UI |
| Cost Meter | 從第一天就有 |
| Trace Log | 含 belief snapshot |

---

## §41 Roadmap

> **Reader**：C-Level / 業務 / 客戶
> **Decision**：時程預期
> **Evidence Needed**：5 個 phase + 每 phase 交付物

### 41.1 Phase 1：客服 Copilot（0-3 個月）

目標：幫真人客服提高效率，不直接自動回覆。

| 交付 | 說明 |
| :--- | :--- |
| Entity Model（電子鎖維修派工） | 七工件齊全 |
| Knowledge ingestion | SOP、FAQ、案例 |
| Hypothesize Layer | 單層 LLM + belief schema v1 |
| Suggested reply | AI 建議答案 |
| Passive Diff Engine | 自動 diff + 卡片式 review |
| Trace log | 含 belief snapshot |
| Basic dashboard | 採用率、節省時間 |
| Cost Meter | 從零實作 |

### 41.2 Phase 2：Shadow Mode（3-6 個月）

目標：AI 在真實對話旁邊實習。

| 交付 | 說明 |
| :--- | :--- |
| Real conversation replay | 用真實歷史對話測試 |
| Human-AI comparison dashboard | 比較真人與 AI 回覆 |
| Error taxonomy | 分類錯誤 |
| Skill proposal queue | 生成候選技能 |
| Evaluation harness | 建立初版測試集 |
| **Eval freshness audit** | 定期 distribution 對比 |
| **Memory drift detection** | drift score 監控 |
| **Reasoning & Cost Router** | 模型 tier routing 上線 |

### 41.3 Phase 3：低風險自動化（6-12 個月）

目標：讓 AI 自動處理低風險任務（FAQ、查詢、補件、預約）。

| 交付 | 說明 |
| :--- | :--- |
| Low-risk automation | L0-L1 工具可自動 |
| Decide + Calibrate Layer | 完整三層 meta-skill 上線 |
| Human handoff（含成功率指標） | 轉人工不只是丟出去 |
| Tool permission layer | L0-L4 分級 |
| Canary release | 小流量灰度 |
| Rollback | 回退上一版本 |
| **Reward model（初版）** | 接 Phase 4 鋪路 |

### 41.4 Phase 4：多租戶平台（12-18 個月）

目標：支援多企業、多品牌、多流程。

| 交付 | 說明 |
| :--- | :--- |
| Tenant isolation | 資料、記憶、工具隔離 |
| Skill registry（belief-condition trigger） | 技能版本化 + 條件式啟用 |
| Tenant dashboard | 每個客戶獨立指標 |
| Policy management | 品牌話術與規則 |
| Compliance controls | 審計與保留政策 |
| **Multi-armed bandit for skill A/B** | 灰度流量分配 |

### 41.5 Phase 5：AI 數位藍領員工生態系（18-36 個月）

| 交付 | 說明 |
| :--- | :--- |
| Vertical skill packs | 電子鎖 → 印章 → 開鎖 → 汽車鑰匙 → 物業 |
| Partner integrations | CRM、ERP、工單、支付、物流 |
| Runtime abstraction | 可替換 agent runtime |
| Skill marketplace | 經審核的技能生態 |
| Workforce analytics | AI 員工績效與成本 |
| **Offline policy evaluation** | 大規模 replay |

---

## §42 Cold Start Strategy

> **Reader**：客戶成功 / 業務 / 平台運營
> **Decision**：新 tenant onboarding 流程
> **Evidence Needed**：Week 0-5 排程、Professional Services 配合

### 42.1 五週 Onboarding

| 階段 | 動作 | 時間 |
| :--- | :--- | :--- |
| Week 0 | SOP 訪談、知識庫盤點、Entity Model 客製化 | 1 週 |
| Week 1-2 | 文檔匯入、初版 skill 配置（用 domain memory 預填） | 1 週 |
| Week 3 | Shadow mode 跑 50-100 通真實對話，產生第一批 candidate | 1 週 |
| Week 4 | Expert calibration session，初步調 belief schema | 1 週 |
| Week 5+ | Copilot 上線 | 持續迭代 |

**這個 onboarding 必須有 professional service 配合，不能純 self-serve**。

---

## §43 Migration & Transition

> **Reader**：客戶 IT / 整合夥伴 / 平台運營
> **Decision**：跨系統遷移路徑
> **Evidence Needed**：3 種遷移場景

### 43.1 客戶從既有客服系統遷移

`[TBD-W2]` — 待補：從 Zendesk / Salesforce / 自建系統遷入的標準流程。

### 43.2 跨 Hermes 版本遷移

對應 ADR-004 Fork-and-Pin：每季 rebase + regression。

### 43.3 跨 LLM Provider 遷移

透過 AgentRuntimeAdapter（§17.3.1）抽象，可替換或並行其他 runtime。

---

## §44 Success Metrics

> **Reader**：C-Level / 業務 / 客戶
> **Decision**：成功與否的量化判定
> **Evidence Needed**：北極星 + 各 phase 指標 + ROI 模型

### 44.1 北極星指標

**Resolved Service Tasks Under Governance**。

### 44.2 各 Phase 指標

詳見 §39.2。

### 44.3 客戶 ROI 指標

`[TBD-W2]` — 待補：訓練週期縮短、人力節省、客訴下降、續約率提升的量化模型。

### 44.4 平台健康度指標

詳見 §32.2 完整 metrics 清單。

---

# Part XI — 風險與決策（Risk & Decisions）

---

## §45 Risk Register

> **Reader**：C-Level / Risk Officer / 採購
> **Decision**：風險可接受度
> **Evidence Needed**：每項風險的 Likelihood × Impact × Mitigation × Owner

### 45.1 完整風險清單

| 類別 | 風險 | 嚴重度 | 緩解 | Owner |
| :--- | :--- | :---: | :--- | :--- |
| 資料 | Cold start 無歷史對話 | 高 | Professional Services + Domain Memory 預填 + Shadow mode | 業務 + PM |
| 資料 | Eval set 與 reality gap | 高 | Eval freshness audit + Passive labeling 為主訊號 | 資料科學家 |
| 資料 | 規模太小無法 fine-tune | 中 | 不做 fine-tune，靠 in-context skill + RAG | 資料科學家 |
| 人因 | 專家不肯主動標註 | 高 | Passive labeling 為主，主動 review 只在 high-value candidate | UX + PM |
| 人因 | 客服主管不會用 trace log | 中 | Dashboard 抽象化、「為什麼這樣回」一句話解釋 | UX |
| 技術 | Hermes 0.x 上游 breaking | 中 | Fork-and-pin、季度 rebase、Adapter 抽象（ADR-004） | 平台 |
| 技術 | Skill 衝突 / 爆炸 | 中 | Belief-condition trigger + Deprecation policy | 平台 |
| 技術 | Memory 漂移 | 中 | Drift detection + Snapshot rollback | 平台 |
| 技術 | Token cost 爆炸 | 中 | Prompt cache + Reasoning & Cost Router + Cost meter | 平台 + CFO |
| 技術 | PII redaction false negative | 高 | 雙層 redaction + 抽樣審核 + acceptable rate < 0.1% | 安全 |
| 系統動態 | 自動化反噬真人技能 | 中 | 自動化率天花板 + 真人 shadow review 保留比例 | 運營 |
| 商業 | LLM provider 自己進場 | 中 | 垂直深度 + 本地服務 + Entity Model 護城河 | 業務 |
| 商業 | 客戶資料權屬阻擋 cross-tenant | 中 | Skill 共享只在 SOP 結構層，不在 raw data 層 | 法遵 |
| 合規 | EU AI Act / 個資法 / 消保法 | 高 | 透明告知、垂直法規對應表、L3+ 工具強制人工批准 | 法遵 |
| 安全 | Prompt injection | 高 | 輸入隔離、攻擊測試集、工具權限 | 安全 |
| 安全 | Memory poisoning | 中 | Drift detection、snapshot rollback、cross-session 治理 | 安全 |

---

## §46 Assumption Register

> **Reader**：Founder / C-Level / 投資人
> **Decision**：哪些假設要驗證、什麼條件下要轉向
> **Evidence Needed**：假設、信心、驗證計畫、觸發條件

`[TBD-W3]` — 待補完整 register。種子假設（從 v2 §17 蘇格拉底批判轉化）：

| Assumption | Confidence | Validation Plan | Trigger（若不成立怎麼辦） |
| :--- | :---: | :--- | :--- |
| 中小企業客服主管會付費 | 中 | Phase 1 PoC 訪談 + 試用轉化率 | 轉向大型品牌 / 連鎖 |
| Hermes-like agent 比自建省工 | 高 | Phase 1 整合工時對比 | 自建 ReAct runtime |
| Passive labeling 信號夠強 | 中 | Phase 2 採用 Phase 1 真實資料驗證 | 加重主動 review 比例 |
| 垂直 Entity Model 是護城河 | 高 | 競品分析、客戶 sign-off | 加深整合深度 |
| 客戶願意接受 1-2 週 onboarding | 中 | Phase 1 採購談判 | 加強 self-serve 流程 |
| LLM provider 不會直接競爭垂直 | 中 | 季度競品掃描 | 加深垂直 + 本地服務 |
| 自動化率 70% 是合理天花板 | 中 | Phase 3 真實數據 | 調整天花板 |

---

## §47 Architecture Decision Records（ADRs）

> **Reader**：開發團隊 / 新加入 Architect / 客戶 EA
> **Decision**：理解為什麼是這樣設計
> **Evidence Needed**：每 ADR 含 Context / Decision / Consequence / Alternatives

### 47.1 已決定的 ADRs

| ID | 標題 | Status |
| :--- | :--- | :---: |
| ADR-001 | 採用 Hypothesis-Driven Runtime（而非 Trigger-Based） | Accepted |
| ADR-002 | Skill.trigger 改為 Belief Condition | Accepted |
| ADR-003 | Passive Label 為主訊號源（取代主動標註為主） | Accepted |
| ADR-004 | Hermes Fork-and-Pin + AgentRuntimeAdapter 抽象 | Accepted |
| ADR-005 | Cross-tenant 預設不共享 Skill（除明確同意 + 匿名化） | Accepted |
| ADR-006 | 不做 On-policy RL on Production | Accepted |
| ADR-007 | 選擇電子鎖維修派工為 Phase 1 Wedge | Accepted |
| ADR-008 | Memory Drift Detection 為必要組件 | Accepted |
| ADR-009 | Three-layer Meta-Skill（Hypothesize/Decide/Calibrate）入 DB | Accepted |
| ADR-010 | Tool Risk Tier L0-L4 分級 + L3+ 強制人工批准 | Accepted |

完整 ADR 文件 `[TBD-W3]`，每條依模板：Context / Decision / Consequences / Alternatives / Date / Author。

---

## §48 RL 導入決策

> **Reader**：CTO / 資料科學家 / 投資人
> **Decision**：何時不該做 RL，何時可以
> **Evidence Needed**：分階段表 + 為何 on-policy RL 不該做

### 48.1 結論先講

```text
Phase 1-3 完全不該碰 RL。
Phase 4+ 可導入「RL 派生工具」（reward model、bandit、offline eval），
但不是真正的 on-policy RL。
On-policy RL on production traffic 永遠不該做。
```

### 48.2 為什麼不該做 on-policy RL

- **Reward 太稀疏**：客戶滿意只在對話結束才知道，多輪 credit assignment 極困難
- **Exploration 太昂貴**：真實用戶不是訓練 episode，探索壞動作直接傷客戶體驗
- **Off-policy correction 不穩定**：多輪對話的 importance sampling 方差大
- **Reward hacking 風險**：AI 可能學會「快速結束對話」而非「解決問題」

### 48.3 RL 派生工具導入時機表

| 階段 | 樣本規模 | 工具 | 為什麼 |
| :--- | :--- | :--- | :--- |
| **Phase 1-2** | < 1k turns | 無 | Supervised + heuristic 已足夠，連 fine-tune 都還做不了 |
| **Phase 3** | 1k - 10k | **Reward model** | 用 expert approval/rejection 訓練 binary classifier，當 inline scorer |
| **Phase 4** | 10k - 50k | **Multi-armed bandit** | Skill 版本灰度時用 bandit 分配流量，比固定 50/50 efficient |
| **Phase 5+** | > 50k | **Offline policy evaluation** | 用歷史對話 replay 做 counterfactual eval |
| **Never** | any | On-policy RL on production | 上述風險 |

### 48.4 Hypothesis-Driven 已吸收 RL 精神

POMDP 框架本來就是 RL 的理論親戚。v2 在 Layer 5 做 belief tracking + action policy **在 prompt 層做近似 POMDP solver**，這是 cost-effective 路線。**不需要真的解 POMDP，更不需要 policy gradient**。

### 48.5 別把 supervised loop 叫 RL

- Supervised：有 label 直接學
- Reward model：用 label 訓練 scorer，scorer 評其他 sample
- RL：scorer 反饋驅動 policy update

平台主要用前兩者，第三者非必要。

對應 ADR-006。

---

# Part XII — 附錄（Appendices）

---

## 附錄 A — Glossary（統一術語表）

> **Reader**：所有 stakeholder
> **Purpose**：跨團隊溝通同義語、避免歧義

`[TBD-W2]` — 待補至 50+ 條。種子清單：

| 術語 | 定義 |
| :--- | :--- |
| **Belief** | 結構化的對情境整體推測，跨輪累積。對應 §12.2 schema。 |
| **Hypothesis** | 對客戶意圖的單一推測，多個 hypothesis 構成 belief。 |
| **likely_misframe** | 客戶可能誤判了什麼。hypothesis-driven 的核心差異欄位。 |
| **Calibration** | 讀客戶反應更新 belief 的動作。 |
| **COMMIT / PROBE / EXPLORE / ESCALATE** | 四種 action type。 |
| **Skill** | 可執行 SOP 單元，belief-condition trigger 啟動。 |
| **Knowledge** | 正式事實（FAQ / 政策 / 規格）。 |
| **Memory** | 過去經驗與偏好，分六層治理。 |
| **Trace** | 含 belief snapshot 的 turn-level audit 紀錄。 |
| **Tenant** | 企業客戶 = 一個 isolated 邏輯空間。 |
| **Author / Owner** | 訊息發送者 vs 帳號擁有者，可不同。 |
| **AgentRuntimeAdapter** | Harness 抽象介面，讓底層 runtime 可替換。 |
| **Cost per Resolved Task** | 完成一個受治理服務任務的總成本。 |
| **Passive Diff Engine** | 自動比對真人實際送出 vs AI 建議。 |
| **Drift Score** | 線上 distribution 與基準的距離。 |
| **Pace-Layered Governance** | 依變動速度分 SoR / SoD / SoI 三層治理。 |
| **Risk Tier L0-L4** | 工具操作的 5 級風險分級。 |
| ... | ... |

---

## 附錄 B — 垂直 Entity Model 範例：電子鎖維修派工

### B.1 Entity Dictionary

```yaml
Device:
  id: string (serial number)
  brand: enum [Chatlock, Dormakaba, Philips, ...]
  model: string
  install_location: {address, floor, position}
  install_date: date
  warranty_status: enum [active, expiring, expired]
  current_state: enum [normal, battery_low, mechanical_issue, network_issue, unknown]

Customer:
  id: string
  type: enum [B2C_end_user, B2B_dealer, B2B_property_manager]
  tier: enum [vip, normal]
  authorized_devices: [Device.id]

ServiceRequest:
  id: string
  customer_id: Customer.id
  device_id: Device.id (nullable until identified)
  symptom_description: text
  symptom_classified: enum [no_power, mechanical_stuck, app_disconnected, ...]
  urgency: enum [locked_out, can_wait, future]
  attachments: [photo, video]
  created_at: timestamp

WorkOrder:
  id: string
  service_request_id: ServiceRequest.id
  technician_id: Technician.id (nullable)
  scheduled_time: timestamp
  parts_reserved: [Part.id]
  state: enum [pending, assigned, in_progress, completed, cancelled]
  sla_target: timestamp

Technician:
  id: string
  skills: [device.brand]
  geo_location: coordinates
  current_load: int

Part:
  id: string
  compatible_models: [Device.model]
  stock_quantity: int
  cost: decimal

SLAContract:
  customer_id: Customer.id
  response_time_target: duration
  resolution_time_target: duration
  penalty_clause: text
```

### B.2 Event Catalog

```yaml
ServiceRequestCreated:
  trigger: customer sends symptom message
  required_belief: primary_intent=support, ownership_status=owned
  side_effects: [create ServiceRequest record, initial classification]

DeviceIdentified:
  trigger: brand + model confirmed
  required_belief: brand_known=true, model_known=true
  side_effects: [link Device to ServiceRequest, load brand-specific SOP]

WorkOrderAssigned:
  trigger: ServiceRequest.symptom_classified is set AND L2 tool authorized
  side_effects: [match technician by skill+location, reserve time slot]

TechnicianDispatched:
  trigger: WorkOrder.scheduled_time approaching
  side_effects: [notify technician, send customer reminder]

PartReserved:
  trigger: symptom_classified requires part
  side_effects: [decrement stock, attach to WorkOrder]

ServiceCompleted:
  trigger: technician confirms
  side_effects: [close WorkOrder, trigger feedback collection, update Device.current_state]

BillingSettled:
  trigger: ServiceCompleted + payment
  side_effects: [release Part reservation, archive WorkOrder]
```

### B.3 State Machine（WorkOrder）

```text
pending ──(技師指派)──→ assigned ──(技師抵達)──→ in_progress ──(完工)──→ completed
   │                          │                          │
   └──(取消)──→ cancelled    └──(改期)──→ pending      └──(失敗)──→ pending
```

### B.4 SOP Graph

`[TBD-W2]` — 待補：每個 SOP 對應的 entity 操作序列圖。

### B.5 Belief Schema Extension（維修派工特化）

通用維度（intent / ownership / urgency / misframe）之外加：

```yaml
domain_dimensions:
  brand_known: bool
  model_known: bool
  device_location_known: bool
  symptom_classified: enum [no_power, mechanical_stuck, app_disconnected, unknown]
  warranty_status: enum [active, expiring, expired, unknown]
  urgency_modifier: enum [locked_out, no_power, can_wait, future]
  technician_dispatch_needed: bool
  parts_required_inferred: [Part.compatible_models]
  participant_role: enum [device_owner, family_member, property_manager, unknown]
```

### B.6 Tool Permission Matrix（部分）

| Tool | 對應 entity 操作 | Risk Level | 自動/批准 |
| :--- | :--- | :--- | :--- |
| `lookup_device_info` | Device.read | L0 | 自動 |
| `lookup_order_status` | WorkOrder.read | L1 | 身份驗證 |
| `create_service_request` | ServiceRequest.write | L2 | 自動 + 客戶確認 |
| `assign_work_order` | WorkOrder.assign | L2 | 自動 + trace |
| `reschedule_work_order` | WorkOrder.update | L2 | 自動 + 客戶確認 |
| `reserve_part` | Part.reserve | L2 | 自動 |
| `cancel_work_order` | WorkOrder.cancel | L3 | 人工批准 |
| `issue_compensation` | Billing.refund | L3 | 人工批准 |
| `commit_sla_penalty` | Contract.penalty | L4 | 禁止自動 |

### B.7 Vertical Glossary（部分）

| 客戶用語 | 可能對應 |
| :--- | :--- |
| 卡卡的 | mechanical_stuck（卡榫）/ battery_low / motor_anomaly |
| 不會動 | no_power / mechanical_lock / app_disconnected |
| 嗶嗶叫 | battery_low / tamper_alarm / wrong_password_lockout |
| 沒反應 | no_power / network_issue / device_dead |
| 鎖頭歹去（台語） | 等同於「鎖壞了」，通常 mechanical |
| 開不起來 | locked_out（緊急）/ no_power / mechanical |

---

## 附錄 C — Belief Schema v3 完整 JSON Schema

`[TBD-W2]` — 待補：完整 JSON Schema with $ref。當前範例見 §12.2。

---

## 附錄 D — AgentRuntimeAdapter OpenAPI 規格

`[TBD-W2]` — 待補：完整 OpenAPI 3.1 spec。當前介面摘要見 §17.3.1。

---

## 附錄 E — Skill Schema 範例

`[TBD-W2]` — 待補：完整 Skill schema with belief-condition trigger example。當前欄位見 §12.3。

---

## 附錄 F — Compliance Matrix 完整表

`[TBD-W2]` — 待補：需求 ↔ 控制 ↔ 證據三向對應完整版（涵蓋 NIST / ISO 27001 / GDPR / 個資法 / EU AI Act / 垂直法規）。

---

## 附錄 G — ATAM Quality Attribute Scenarios 集合

`[TBD-W3]` — 待補：15+ 場景，每場景含：

```text
Source: [刺激源頭，例如：High-volume tenant]
Stimulus: [刺激內容，例如：10x traffic spike]
Artifact: [受影響系統，例如：Hypothesis Engine]
Environment: [運行條件，例如：Production]
Response: [系統應對，例如：Fall back to Haiku tier]
Response Measure: [量化標準，例如：P95 latency < 5s, no dropped messages]
```

---

## 附錄 H — References & Standards

- Hermes Agent GitHub Repository：https://github.com/NousResearch/hermes-agent
- Hermes Agent Persistent Memory：https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md
- Gartner, Agentic AI customer service prediction, 2025-03-05：https://www.gartner.com/en/newsroom/press-releases/2025-03-05-gartner-predicts-agentic-ai-will-autonomously-resolve-80-percent-of-common-customer-service-issues-without-human-intervention-by-20290
- Gartner, Customer-facing conversational GenAI survey, 2024-12-09：https://www.gartner.com/en/newsroom/press-releases/2024-12-09-gartner-survey-reveals-85-percent-of-customer-service-leaders-will-explore-or-pilot-customer-facing-conversational-genai-in-2025
- NIST AI RMF Generative AI Profile, 2024-07-26：https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
- OWASP Top 10 for LLM Applications：https://owasp.org/www-project-top-10-for-large-language-model-applications/
- EU AI Act Article 50 Transparency Obligations：https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50
- ISO/IEC/IEEE 42010:2022 Systems and software engineering — Architecture description
- TOGAF 9.2 — The Open Group Architecture Framework
- C4 Model — https://c4model.com/
- Gartner Pace-Layered Application Strategy
- Yao et al., 2022, ReAct: Synergizing Reasoning and Acting in Language Models
- Peirce on Abductive Reasoning（Stanford Encyclopedia of Philosophy）
- BIZBOK — Business Architecture Body of Knowledge
- ATAM — Architecture Tradeoff Analysis Method（SEI）

---

## 附錄 I — Change Log

| 版本 | 日期 | 主要變更 |
| :--- | :--- | :--- |
| v1 | 2026-05-12（早） | 初版產品白皮書 |
| v1.1 | 2026-05-12（中） | 補上 Reasoning & Cost Router、Harness 即員工、多用戶學習管線、K/M/S 三者分立、Cost per Resolved Task |
| v2 強化版 | 2026-05-12（晚） | 整合 Hypothesis-Driven Runtime（Layer 5）、補 Entity Model 工程、Passive Feedback 為主訊號、Token Economics、RL 決策表、垂直法規對應、系統動態（causal loop）、SWOT 完整化、Hermes 0.x fork-and-pin、語言/時空/離線維度 |
| **v3 EA 結構重整版（W1）** | **2026-05-12** | **套用 TOGAF + ISO 42010 + C4 + Pace-Layered；重排為 12 Parts / 48 章節 / 10 附錄；補 Stakeholder & Concerns Matrix、Capability Map、Value Streams、Conceptual Data Model、C4 三層視圖、Service Catalog、Compliance Matrix 等骨架；舊內容按對映表搬家；缺口以 `[TBD-W2]` / `[TBD-W3]` 標記** |

### v3 W1 完成項
- 12 Parts / 48 章節 / 10 附錄 骨架建立
- Stakeholder & Concerns Matrix（§3）
- Architecture Principles 正式化（§4）
- 七層架構升級為 C4 Container View（§16）
- Conversation Runtime Layer 獨立為核心章節（§17.2）
- AgentRuntimeAdapter 介面條列（§17.3.1）
- ADR 清單建立（§47，10 條）
- Glossary 種子（附錄 A）
- 各章節加上 Reader / Decision / Evidence Needed 三行 header

### v3 W2 待補項（標 [TBD-W2]）
- C4 L1 System Context 完整圖
- C4 L3 Component View 內部細節（§17.4.3、§17.5.2、§17.7.x）
- Sequence Diagrams 4 條完整圖（§19）
- Service Catalog & API Inventory（§20）
- Integration Patterns 完整表（§21）
- External Integrations 規格（§22）
- Technology Stack 完整選型（§23）
- Deployment View（§24）
- Reference Architectures 3 種（§25）
- Threat Model STRIDE/DREAD（§26.2-26.3）
- Security Controls 細節（§27.1、§27.4）
- Compliance Matrix 完整版（§28、附錄 F）
- Privacy by Design（§29）
- NFR 量化（§30-§33）
- Operations Model RACI / Incident Response（§38）
- Migration Playbook（§43）
- ROI 模型（§44.3）
- Belief Schema JSON Schema（附錄 C）
- AgentRuntimeAdapter OpenAPI（附錄 D）
- Skill Schema 完整範例（附錄 E）
- Glossary 擴充至 50+ 條（附錄 A）
- 各 sub-system 內部 components 完整化

### v3 W3 待補項（標 [TBD-W3]）
- ADR-001 至 ADR-010 完整文件
- Assumption Register（§46）
- ATAM Quality Attribute Scenarios 15+（§35、附錄 G）

---

## 附錄 J — Distribution & Approval Sign-off

`[TBD-W3]` — 待補：受眾分版 distribution list、approval routing、signature block。

---

**文件結束**

— v3 W1 結構重整版完成於 2026-05-12 —
